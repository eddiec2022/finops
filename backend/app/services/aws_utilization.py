import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import boto3
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.aws_cpu_metrics import AWS_CPU_METRIC_BY_RESOURCE_TYPE

# Not explicitly listed as its own scope item in Task 20's text, but inferred
# as a necessary prerequisite: rightsizing and non-peak-scheduling both read
# CPU utilization from the already-synced UtilizationMetric table (same
# sync-then-read architecture as Azure, not a live call at recommendation
# time), and nothing built that sync path for AWS before this task - Task 19
# only covered inventory and cost. Mirrors azure_utilization.py's shape.

GRANULARITY_SECONDS = 3600  # 1 hour, matching azure_utilization.GRANULARITY

# Namespace + dimension name CloudWatch needs to identify a resource's metrics
# - unlike Azure Monitor's query_resource (which takes the full ARM resource
# URI and resolves this itself), CloudWatch needs these supplied explicitly
# per service. Only EC2 for v1 (see aws_cpu_metrics.py).
_NAMESPACE_AND_DIMENSION_BY_RESOURCE_TYPE: dict[str, tuple[str, str]] = {
    "aws::ec2::instance": ("AWS/EC2", "InstanceId"),
}


@dataclass
class AwsUtilizationSyncSummary:
    resources_processed: int
    metrics_found: int
    created: int
    updated: int


def map_metric_response(response: Any, metric_name: str) -> list[dict[str, Any]]:
    """Flatten one CloudWatch GetMetricStatistics response into normalized rows.

    A datapoint with no Average is skipped - mirrors azure_utilization's own
    "gap in the series" handling, though real API-shape difference worth
    noting: CloudWatch's documented behavior is to simply omit a period with no
    data from Datapoints entirely, never return a point with a null Average -
    this check is defensive, not something observed happening.
    """
    rows: list[dict[str, Any]] = []
    for point in response.get("Datapoints", []):
        if point.get("Average") is None:
            continue
        rows.append(
            {
                "metric_name": metric_name,
                "unit": point.get("Unit", "Percent"),
                "timestamp": point["Timestamp"],
                "value": point["Average"],
            }
        )
    return rows


def _query_metric(
    client: Any, namespace: str, dimension_name: str, resource_id: str, metric_name: str, lookback_days: int
) -> Any:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    return client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=[{"Name": dimension_name, "Value": resource_id}],
        StartTime=start,
        EndTime=end,
        Period=GRANULARITY_SECONDS,
        Statistics=["Average"],
    )


def fetch_metrics(
    resource_type: str,
    resource_id: str,
    metric_names: list[str],
    lookback_days: int,
    query_metric: Callable[[str, str, str, str, int], Any] | None = None,
) -> list[dict[str, Any]]:
    """Query CloudWatch for each named metric on a single resource.

    Real API-shape difference from Azure Monitor, found writing this: a metric
    CloudWatch has no data for returns a normal response with an empty
    Datapoints list, not an error - unlike Azure Monitor's HttpResponseError
    for a metric that isn't valid for a given resource (which azure_utilization
    catches and treats as "no data for this metric"). Nothing to catch here;
    map_metric_response naturally produces zero rows for an empty response.
    """
    namespace, dimension_name = _NAMESPACE_AND_DIMENSION_BY_RESOURCE_TYPE[resource_type]
    if query_metric is None:
        session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        client = session.client("cloudwatch")
        query_metric = lambda ns, dim, rid, name, days: _query_metric(client, ns, dim, rid, name, days)  # noqa: E731

    rows: list[dict[str, Any]] = []
    for metric_name in metric_names:
        response = query_metric(namespace, dimension_name, resource_id, metric_name, lookback_days)
        rows.extend(map_metric_response(response, metric_name))
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


def sync_aws_utilization(
    db: Session,
    fetch: Callable[[str, str, list[str], int], list[dict[str, Any]]] = fetch_metrics,
) -> AwsUtilizationSyncSummary:
    resources = db.query(Resource).filter(Resource.resource_type.in_(AWS_CPU_METRIC_BY_RESOURCE_TYPE.keys())).all()

    metrics_found = 0
    created = 0
    updated = 0

    for resource in resources:
        metric_names = [AWS_CPU_METRIC_BY_RESOURCE_TYPE[resource.resource_type]]
        # The instance ID CloudWatch's dimension needs, not the ARN - stored in
        # raw_metadata by aws_inventory.parse_arn during inventory sync.
        raw_resource_id = (resource.raw_metadata or {}).get("resource_id")
        if not raw_resource_id:
            continue
        rows = fetch(resource.resource_type, raw_resource_id, metric_names, settings.idle_lookback_days)
        metrics_found += len(rows)
        c, u = upsert_metrics(db, resource.id, rows)
        created += c
        updated += u

    return AwsUtilizationSyncSummary(
        resources_processed=len(resources),
        metrics_found=metrics_found,
        created=created,
        updated=updated,
    )
