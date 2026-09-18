import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.azure_inventory import get_or_create_cloud_account
from app.services.cost_lookup import get_resource_daily_costs
from app.services.cpu_metrics import CPU_METRIC_BY_RESOURCE_TYPE
from app.services.forecasting.linear_burn_rate import LinearBurnRateModel
from app.services.sku_heuristics import SkuSuggestion, suggest_app_service_tier, suggest_vm_sku
from app.services.utilization_evaluation import evaluate_cpu_utilization


def estimate_monthly_savings(
    avg_daily_cost: float | None, cores_reduction_fraction: float | None
) -> tuple[float | None, str]:
    if avg_daily_cost is None:
        return None, "No cost data found for this resource in the lookback window; savings can't be estimated."
    if cores_reduction_fraction is None:
        return None, "No specific suggested size to compare against; savings can't be estimated."

    savings = avg_daily_cost * cores_reduction_fraction * 30
    note = (
        "Approximate: current average daily cost over the lookback window x 30, scaled by the "
        "suggested SKU's core reduction, assuming cost scales linearly with core count within "
        "the same series. Not a billing quote."
    )
    return round(savings, 2), note


def _suggest_sku(resource: Resource) -> SkuSuggestion:
    if resource.resource_type == "microsoft.compute/virtualmachines":
        return suggest_vm_sku(resource.sku)
    return suggest_app_service_tier(resource.sku)


def build_rightsizing_recommendations(
    db: Session, cloud_account_id: uuid.UUID | None = None
) -> dict[str, Any]:
    if cloud_account_id is None:
        # Phase 1 is single-subscription, same convention as forecast.py.
        cloud_account_id = get_or_create_cloud_account(db, settings.azure_subscription_id).id

    cost_model = LinearBurnRateModel(trailing_window_days=settings.idle_lookback_days)

    resources = (
        db.query(Resource)
        .filter(Resource.cloud_account_id == cloud_account_id)
        .filter(Resource.resource_type.in_(CPU_METRIC_BY_RESOURCE_TYPE.keys()))
        .all()
    )

    recommendations = []
    for resource in resources:
        metric_name = CPU_METRIC_BY_RESOURCE_TYPE[resource.resource_type]
        readings = (
            db.query(UtilizationMetric.timestamp, UtilizationMetric.value)
            .filter_by(resource_id=resource.id, metric_name=metric_name)
            .all()
        )
        cpu_result = evaluate_cpu_utilization(
            [(ts, value) for ts, value in readings],
            lookback_days=settings.idle_lookback_days,
            idle_threshold_percent=settings.idle_cpu_threshold_percent,
        )

        # Insufficient history: excluded outright, not flagged on a partial
        # average. Not idle: not a rightsizing candidate, so also excluded.
        if cpu_result.insufficient_data or not cpu_result.is_idle:
            continue

        sku_suggestion = _suggest_sku(resource)

        daily_costs = get_resource_daily_costs(db, resource.id)
        cost_result = cost_model.forecast(daily_costs, horizon_days=1)
        avg_daily_cost = None if cost_result.insufficient_data else cost_result.daily_rate
        estimated_monthly_savings, savings_note = estimate_monthly_savings(
            avg_daily_cost, sku_suggestion.cores_reduction_fraction
        )

        recommendations.append(
            {
                "resource_id": str(resource.id),
                "external_resource_id": resource.external_resource_id,
                "resource_type": resource.resource_type,
                "resource_group": resource.resource_group,
                "region": resource.region,
                "current_sku": resource.sku,
                "suggested_sku": sku_suggestion.suggested_sku,
                "suggestion_note": sku_suggestion.note,
                "avg_cpu_percent": round(cpu_result.avg_cpu_percent, 2),
                "lookback_days": settings.idle_lookback_days,
                "estimated_monthly_savings": estimated_monthly_savings,
                "savings_note": savings_note,
            }
        )

    return {
        "idle_cpu_threshold_percent": settings.idle_cpu_threshold_percent,
        "idle_lookback_days": settings.idle_lookback_days,
        "recommendations": recommendations,
    }
