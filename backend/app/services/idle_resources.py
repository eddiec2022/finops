import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource import Resource
from app.services.azure_inventory import get_or_create_cloud_account
from app.services.cost_lookup import get_resource_daily_costs
from app.services.forecasting.linear_burn_rate import LinearBurnRateModel
from app.services.idle_resource_detection import (
    IdleCheckResult,
    detect_stopped_not_deallocated_vm,
    detect_unattached_disk,
    detect_unused_public_ip,
)

# Maps each covered resource_type to its (reason slug, detector function).
# The reason slug is the machine-readable value in each recommendation's
# `reason` field; `detect_fn`'s human-readable `detail` carries the specific
# evidence (e.g. the exact diskState/powerState value observed).
IDLE_CHECKS: dict[str, tuple[str, Callable[[dict], IdleCheckResult]]] = {
    "microsoft.compute/disks": ("unattached_disk", detect_unattached_disk),
    "microsoft.network/publicipaddresses": ("unused_public_ip", detect_unused_public_ip),
    "microsoft.compute/virtualmachines": ("stopped_not_deallocated_vm", detect_stopped_not_deallocated_vm),
}


def estimate_monthly_waste(avg_daily_cost: float | None) -> tuple[float | None, str]:
    if avg_daily_cost is None:
        return None, "No cost data found for this resource in the lookback window; waste can't be estimated."

    note = (
        "Approximate: current average daily cost over the lookback window x 30, assuming the full "
        "cost is avoidable once the underlying issue (attach the disk, associate or release the IP, "
        "deallocate the VM) is resolved. Not a billing quote."
    )
    return round(avg_daily_cost * 30, 2), note


def build_idle_resource_recommendations(
    db: Session, cloud_account_id: uuid.UUID | None = None
) -> dict[str, Any]:
    if cloud_account_id is None:
        # Phase 1 is single-subscription, same convention as forecast.py/rightsizing.py.
        cloud_account_id = get_or_create_cloud_account(db, settings.azure_subscription_id).id

    cost_model = LinearBurnRateModel(trailing_window_days=settings.idle_lookback_days)

    resources = (
        db.query(Resource)
        .filter(Resource.cloud_account_id == cloud_account_id)
        .filter(Resource.resource_type.in_(IDLE_CHECKS.keys()))
        .all()
    )

    recommendations = []
    for resource in resources:
        reason, detect_fn = IDLE_CHECKS[resource.resource_type]
        result = detect_fn(resource.raw_metadata or {})
        if not result.is_flagged:
            continue

        daily_costs = get_resource_daily_costs(db, resource.id)
        cost_result = cost_model.forecast(daily_costs, horizon_days=1)
        avg_daily_cost = None if cost_result.insufficient_data else cost_result.daily_rate
        estimated_monthly_waste, waste_note = estimate_monthly_waste(avg_daily_cost)

        recommendations.append(
            {
                "resource_id": str(resource.id),
                "external_resource_id": resource.external_resource_id,
                "resource_type": resource.resource_type,
                "resource_group": resource.resource_group,
                "region": resource.region,
                "reason": reason,
                "detail": result.detail,
                "estimated_monthly_waste": estimated_monthly_waste,
                "waste_note": waste_note,
            }
        )

    return {
        "idle_lookback_days": settings.idle_lookback_days,
        "recommendations": recommendations,
    }
