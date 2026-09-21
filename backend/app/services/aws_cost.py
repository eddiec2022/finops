import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import boto3
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cost_record import CostRecord
from app.models.resource import Resource
from app.services.aws_inventory import get_or_create_aws_cloud_account

# Real API-shape finding, discovered writing this against the boto3/moto docs
# (flag for Task 20's live pass): GOV-002 2.4 named `GetCostAndUsage`, but that
# operation has NO resource-level dimension to group by at all - RESOURCE_ID is
# only available on the separate `GetCostAndUsageWithResources` operation, which
# this module uses instead so cost_records.resource_id can be populated the same
# way Azure's is. Two real constraints come with it that GetCostAndUsage doesn't
# have: (1) it only returns data for the trailing 14 days, not an arbitrary
# lookback window - settings.cost_lookback_days (90, shared with Azure) is capped
# to this for AWS specifically; (2) it requires "Resource IDs" to be turned on in
# the account's Cost Explorer preferences, which is an account-level opt-in
# setting, not guaranteed on by default - if it's off, every group's resource-id
# key comes back empty and every AWS cost row will land as non-attributable
# (resource_id=None) rather than erroring, so this may need a one-time manual
# step in the real account before Task 20's per-resource verification works.
AWS_RESOURCE_LEVEL_MAX_LOOKBACK_DAYS = 14

RESOURCE_ID_KEY = "RESOURCE_ID"
RECORD_TYPE_KEY = "RECORD_TYPE"


@dataclass
class AwsCostSyncSummary:
    found: int
    created: int
    updated: int


def fetch_cost_rows(account_id: str, lookback_days: int) -> Any:
    """Query AWS Cost Explorer for daily amortized cost, grouped by resource and record type."""
    session = boto3.Session(
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
    client = session.client("ce")

    capped_lookback = min(lookback_days, AWS_RESOURCE_LEVEL_MAX_LOOKBACK_DAYS)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=capped_lookback)

    return client.get_cost_and_usage_with_resources(
        TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
        Granularity="DAILY",
        Metrics=["AmortizedCost"],
        GroupBy=[
            {"Type": "DIMENSION", "Key": RESOURCE_ID_KEY},
            {"Type": "DIMENSION", "Key": RECORD_TYPE_KEY},
        ],
    )


def map_cost_response(response: Any) -> list[dict[str, Any]]:
    """Flatten a GetCostAndUsageWithResources response into normalized cost rows.

    Mirrors azure_cost.map_cost_response's empty-string-means-non-attributable
    convention: an empty (or missing) resource-id group key becomes None, same
    as Azure's ResourceId dimension.
    """
    rows: list[dict[str, Any]] = []
    for result in response.get("ResultsByTime", []):
        row_date = date.fromisoformat(result["TimePeriod"]["Start"])
        for group in result.get("Groups", []):
            keys = group.get("Keys", [])
            resource_arn = keys[0] if len(keys) > 0 and keys[0] else None
            record_type = keys[1] if len(keys) > 1 else "Usage"
            amount = group.get("Metrics", {}).get("AmortizedCost", {})
            rows.append(
                {
                    "date": row_date,
                    "external_resource_id": resource_arn,
                    "charge_type": record_type,
                    "currency": amount.get("Unit", "USD"),
                    "amortized_cost": float(amount.get("Amount", 0)),
                }
            )
    return rows


def _resolve_resource_id(db: Session, external_resource_id: str | None) -> uuid.UUID | None:
    if not external_resource_id:
        return None
    # Same case-insensitive lookup azure_cost.py uses, for the same reason -
    # ARNs are typically stable-case, but there's no guarantee Cost Explorer's
    # casing always matches exactly what the inventory connector stored.
    resource = (
        db.query(Resource).filter(func.lower(Resource.external_resource_id) == external_resource_id.lower()).one_or_none()
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


def sync_aws_cost(
    db: Session, fetch: Callable[[str, int], Any] = fetch_cost_rows
) -> AwsCostSyncSummary:
    account_id = settings.aws_account_id
    response = fetch(account_id, settings.cost_lookback_days)
    mapped_rows = map_cost_response(response)
    cloud_account = get_or_create_aws_cloud_account(db, account_id)
    created, updated = upsert_cost_records(db, cloud_account.id, mapped_rows)
    return AwsCostSyncSummary(found=len(mapped_rows), created=created, updated=updated)
