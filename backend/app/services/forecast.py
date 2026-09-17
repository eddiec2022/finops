import uuid
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cost_record import CostRecord
from app.models.resource import Resource
from app.services.azure_inventory import get_or_create_cloud_account
from app.services.forecasting.base import ForecastModel, ForecastPoint
from app.services.forecasting.linear_burn_rate import LinearBurnRateModel

# Standard dashboard rollup windows. horizon_days itself is always included too,
# even when it doesn't match one of these, so a request for e.g. horizon_days=45
# still gets a rollup that actually reflects what was projected.
STANDARD_ROLLUP_WINDOWS = (7, 30, 90)


def get_daily_costs(
    db: Session,
    cloud_account_id: uuid.UUID,
    resource_group: str | None = None,
    resource_type: str | None = None,
) -> list[tuple[date, float]]:
    query = db.query(CostRecord.date, func.sum(CostRecord.amortized_cost)).filter(
        CostRecord.cloud_account_id == cloud_account_id
    )
    if resource_group or resource_type:
        # A resource_group/resource_type filter can only match cost rows that
        # are attributable to a resource - non-attributable charges (resource_id
        # null) are naturally excluded here via the inner join, unlike the
        # unfiltered aggregate view which includes them.
        query = query.join(Resource, Resource.id == CostRecord.resource_id)
        if resource_group:
            query = query.filter(Resource.resource_group == resource_group)
        if resource_type:
            query = query.filter(Resource.resource_type == resource_type)
    query = query.group_by(CostRecord.date).order_by(CostRecord.date)
    return [(row_date, float(total)) for row_date, total in query.all()]


def build_rollups(points: list[ForecastPoint], horizon_days: int) -> dict[int, float]:
    windows = sorted({w for w in STANDARD_ROLLUP_WINDOWS if w <= horizon_days} | {horizon_days})
    return {window: sum(p.projected_cost for p in points[:window]) for window in windows}


def build_forecast(
    db: Session,
    horizon_days: int,
    resource_group: str | None = None,
    resource_type: str | None = None,
    cloud_account_id: uuid.UUID | None = None,
    model: ForecastModel | None = None,
) -> dict[str, Any]:
    model = model or LinearBurnRateModel()
    if cloud_account_id is None:
        # Phase 1 is single-subscription: default to the configured Azure
        # subscription's account. Once AWS/GCP data lands in this same
        # cost_records table, an unscoped query would wrongly mix providers -
        # this keeps the seam explicit rather than leaving it unscoped.
        cloud_account_id = get_or_create_cloud_account(db, settings.azure_subscription_id).id

    daily_costs = get_daily_costs(db, cloud_account_id, resource_group=resource_group, resource_type=resource_type)
    result = model.forecast(daily_costs, horizon_days)

    if result.insufficient_data:
        return {
            "insufficient_data": True,
            "daily_rate": None,
            "horizon_days": horizon_days,
            "rollups": {},
            "series": [],
        }

    return {
        "insufficient_data": False,
        "daily_rate": result.daily_rate,
        "horizon_days": horizon_days,
        "rollups": build_rollups(result.points, horizon_days),
        "series": [{"date": p.date.isoformat(), "projected_cost": p.projected_cost} for p in result.points],
    }
