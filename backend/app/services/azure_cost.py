import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from azure.identity import ClientSecretCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    ExportType,
    FunctionType,
    GranularityType,
    QueryAggregation,
    QueryColumnType,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
    TimeframeType,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cost_record import CostRecord
from app.models.resource import Resource
from app.services.azure_inventory import get_or_create_cloud_account

RESOURCE_ID_COLUMN = "ResourceId"
CHARGE_TYPE_COLUMN = "ChargeType"
DATE_COLUMN = "UsageDate"
COST_COLUMN = "Cost"
CURRENCY_COLUMN = "Currency"


@dataclass
class CostSyncSummary:
    found: int
    created: int
    updated: int


def fetch_cost_rows(subscription_id: str, lookback_days: int) -> Any:
    """Query Azure Cost Management for daily amortized cost, grouped by resource and charge type."""
    credential = ClientSecretCredential(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    client = CostManagementClient(credential)
    scope = f"/subscriptions/{subscription_id}"

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    query = QueryDefinition(
        type=ExportType.AMORTIZED_COST,
        timeframe=TimeframeType.CUSTOM,
        time_period=QueryTimePeriod(from_property=start, to=end),
        dataset=QueryDataset(
            granularity=GranularityType.DAILY,
            aggregation={"Cost": QueryAggregation(name="Cost", function=FunctionType.SUM)},
            grouping=[
                QueryGrouping(type=QueryColumnType.DIMENSION, name=RESOURCE_ID_COLUMN),
                QueryGrouping(type=QueryColumnType.DIMENSION, name=CHARGE_TYPE_COLUMN),
            ],
        ),
    )
    return client.query.usage(scope, query)


def _parse_usage_date(value: Any) -> date:
    """Cost Management returns UsageDate as an int in YYYYMMDD form (e.g. 20260917), not an ISO string."""
    return datetime.strptime(str(int(value)), "%Y%m%d").date()


def map_cost_response(response: Any) -> list[dict[str, Any]]:
    """Flatten a Cost Management query response into normalized cost rows.

    Column order in the response isn't guaranteed, so every value is looked up by
    the column's name rather than a fixed position.
    """
    columns = [c.name for c in response.columns]
    index = {name: i for i, name in enumerate(columns)}

    rows: list[dict[str, Any]] = []
    for raw_row in response.rows:
        # Cost Management returns an empty string (not null) for ResourceId when
        # a charge isn't attributable to a single resource.
        resource_id_raw = raw_row[index[RESOURCE_ID_COLUMN]] or None
        rows.append(
            {
                "date": _parse_usage_date(raw_row[index[DATE_COLUMN]]),
                "external_resource_id": resource_id_raw,
                "charge_type": raw_row[index[CHARGE_TYPE_COLUMN]],
                "currency": raw_row[index[CURRENCY_COLUMN]],
                "amortized_cost": raw_row[index[COST_COLUMN]],
            }
        )
    return rows


def _resolve_resource_id(db: Session, external_resource_id: str | None) -> uuid.UUID | None:
    if not external_resource_id:
        return None
    # Azure resource IDs are canonically case-insensitive, and Cost Management's
    # ResourceId dimension doesn't always match Resource Graph's casing (e.g. the
    # resource group segment) for the same resource.
    resource = (
        db.query(Resource)
        .filter(func.lower(Resource.external_resource_id) == external_resource_id.lower())
        .one_or_none()
    )
    return resource.id if resource else None


def upsert_cost_records(db: Session, cloud_account_id: uuid.UUID, rows: list[dict[str, Any]]) -> tuple[int, int]:
    created = 0
    updated = 0
    for row in rows:
        resource_id = _resolve_resource_id(db, row["external_resource_id"])
        existing = (
            db.query(CostRecord)
            .filter_by(
                cloud_account_id=cloud_account_id,
                resource_id=resource_id,
                date=row["date"],
                charge_type=row["charge_type"],
            )
            .one_or_none()
        )
        if existing is None:
            db.add(
                CostRecord(
                    cloud_account_id=cloud_account_id,
                    resource_id=resource_id,
                    date=row["date"],
                    amortized_cost=row["amortized_cost"],
                    currency=row["currency"],
                    granularity="Daily",
                    charge_type=row["charge_type"],
                )
            )
            created += 1
        else:
            existing.amortized_cost = row["amortized_cost"]
            existing.currency = row["currency"]
            updated += 1
    db.commit()
    return created, updated


def sync_cost(
    db: Session,
    fetch: Callable[[str, int], Any] = fetch_cost_rows,
) -> CostSyncSummary:
    subscription_id = settings.azure_subscription_id
    response = fetch(subscription_id, settings.cost_lookback_days)
    mapped_rows = map_cost_response(response)
    cloud_account = get_or_create_cloud_account(db, subscription_id)
    created, updated = upsert_cost_records(db, cloud_account.id, mapped_rows)
    return CostSyncSummary(found=len(mapped_rows), created=created, updated=updated)
