import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource import Resource
from app.services.aws_idle_resource_detection import (
    IdleCheckResult,
    detect_stopped_ec2_instance,
    detect_unassociated_elastic_ip,
    detect_unattached_ebs_volume,
)
from app.services.aws_inventory import get_or_create_aws_cloud_account
from app.services.cost_lookup import get_resource_daily_costs
from app.services.forecasting.linear_burn_rate import LinearBurnRateModel

# Maps each covered resource_type to its (reason slug, detector function) -
# direct AWS analogues of idle_resources.IDLE_CHECKS' three Azure checks.
IDLE_CHECKS: dict[str, tuple[str, Callable[[dict], IdleCheckResult]]] = {
    "aws::ec2::volume": ("unattached_ebs_volume", detect_unattached_ebs_volume),
    "aws::ec2::elastic-ip": ("unassociated_elastic_ip", detect_unassociated_elastic_ip),
    "aws::ec2::instance": ("stopped_ec2_instance", detect_stopped_ec2_instance),
}


def estimate_monthly_waste(avg_daily_cost: float | None) -> tuple[float | None, str]:
    """Identical logic to idle_resources.estimate_monthly_waste - reused as a
    plain function rather than imported, since the wording ("attach the disk,
    associate or release the IP, deallocate the VM") is Azure-specific remediation
    language that doesn't apply verbatim to AWS's own remediation steps."""
    if avg_daily_cost is None:
        return None, "No cost data found for this resource in the lookback window; waste can't be estimated."

    note = (
        "Approximate: current average daily cost over the lookback window x 30, assuming the full "
        "cost is avoidable once the underlying issue (attach the volume, associate or release the "
        "Elastic IP, terminate the stopped instance) is resolved. Not a billing quote."
    )
    return round(avg_daily_cost * 30, 2), note


def build_aws_idle_resource_recommendations(
    db: Session, cloud_account_id: uuid.UUID | None = None
) -> dict[str, Any]:
    if cloud_account_id is None:
        cloud_account_id = get_or_create_aws_cloud_account(db, settings.aws_account_id).id

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
                "provider": "aws",
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
