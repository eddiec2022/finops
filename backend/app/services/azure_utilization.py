import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from azure.core.exceptions import HttpResponseError
from azure.identity import ClientSecretCredential
from azure.monitor.query import MetricAggregationType, MetricsQueryClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric

GRANULARITY = timedelta(hours=1)

# Resource types this connector covers, and the Azure Monitor platform metrics to
# pull for each. VM memory requires the guest diagnostics/AMA extension and often
# isn't registered as a valid metric for a given VM - queried per-metric (see
# fetch_metrics) so that failure doesn't take down the other metrics.
# App Service has no platform disk I/O metric equivalent to a VM's, so it's
# omitted for that resource type rather than mapped to something that doesn't exist.
RESOURCE_TYPE_METRICS: dict[str, list[str]] = {
    "microsoft.compute/virtualmachines": [
        "Percentage CPU",
        "Available Memory Bytes",
        "Disk Read Bytes",
        "Disk Write Bytes",
        "Network In Total",
        "Network Out Total",
    ],
    "microsoft.web/sites": [
        "CpuPercentage",
        "MemoryPercentage",
        "BytesReceived",
        "BytesSent",
    ],
}


@dataclass
class UtilizationSyncSummary:
    resources_processed: int
    metrics_found: int
    created: int
    updated: int


def map_metric_response(response: Any) -> list[dict[str, Any]]:
    """Flatten one Azure Monitor metrics response into normalized metric rows.

    A data point with no average (a gap in the series, or the metric existing but
    unreported for that hour) is skipped rather than stored as a null/zero value.
    """
    rows: list[dict[str, Any]] = []
    for metric in response.metrics:
        unit = str(metric.unit)
        for series in metric.timeseries:
            for point in series.data:
                if point.average is None:
                    continue
                rows.append(
                    {
                        "metric_name": metric.name,
                        "unit": unit,
                        "timestamp": point.timestamp,
                        "value": point.average,
                    }
                )
    return rows


def _query_metric(client: MetricsQueryClient, resource_uri: str, metric_name: str, lookback_days: int) -> Any:
    return client.query_resource(
        resource_uri,
        metric_names=[metric_name],
        timespan=timedelta(days=lookback_days),
        granularity=GRANULARITY,
        aggregations=[MetricAggregationType.AVERAGE],
    )


def fetch_metrics(
    resource_uri: str,
    metric_names: list[str],
    lookback_days: int,
    query_metric: Callable[[str, str, int], Any] | None = None,
) -> list[dict[str, Any]]:
    """Query Azure Monitor for each named metric on a single resource.

    Each metric is queried independently: a metric that isn't valid for this
    particular resource (e.g. VM memory without the guest diagnostics extension)
    raises HttpResponseError from the SDK, which is treated as "no data for this
    metric" rather than failing the whole resource.
    """
    if query_metric is None:
        credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
        client = MetricsQueryClient(credential)
        query_metric = lambda uri, name, days: _query_metric(client, uri, name, days)  # noqa: E731

    rows: list[dict[str, Any]] = []
    for metric_name in metric_names:
        try:
            response = query_metric(resource_uri, metric_name, lookback_days)
        except HttpResponseError:
            continue
        rows.extend(map_metric_response(response))
    return rows


def upsert_metrics(db: Session, resource_id: uuid.UUID, rows: list[dict[str, Any]]) -> tuple[int, int]:
    created = 0
    updated = 0
    for row in rows:
        existing = (
            db.query(UtilizationMetric)
            .filter_by(resource_id=resource_id, metric_name=row["metric_name"], timestamp=row["timestamp"])
            .one_or_none()
        )
        if existing is None:
            db.add(
                UtilizationMetric(
                    resource_id=resource_id,
                    metric_name=row["metric_name"],
                    timestamp=row["timestamp"],
                    value=row["value"],
                    unit=row["unit"],
                )
            )
            created += 1
        else:
            existing.value = row["value"]
            existing.unit = row["unit"]
            updated += 1
    db.commit()
    return created, updated


def sync_utilization(
    db: Session,
    fetch: Callable[[str, list[str], int], list[dict[str, Any]]] = fetch_metrics,
) -> UtilizationSyncSummary:
    resources = db.query(Resource).filter(Resource.resource_type.in_(RESOURCE_TYPE_METRICS.keys())).all()

    metrics_found = 0
    created = 0
    updated = 0

    for resource in resources:
        metric_names = RESOURCE_TYPE_METRICS[resource.resource_type]
        rows = fetch(resource.external_resource_id, metric_names, settings.idle_lookback_days)
        metrics_found += len(rows)
        c, u = upsert_metrics(db, resource.id, rows)
        created += c
        updated += u

    return UtilizationSyncSummary(
        resources_processed=len(resources),
        metrics_found=metrics_found,
        created=created,
        updated=updated,
    )
