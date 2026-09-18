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
from app.services.non_prod_heuristics import detect_non_prod_by_name, detect_non_prod_by_tag
from app.services.peak_usage_evaluation import (
    BUSINESS_DAYS,
    BUSINESS_HOURS_END_UTC,
    BUSINESS_HOURS_START_UTC,
    evaluate_peak_off_peak_usage,
)

BUSINESS_HOURS_DEFINITION = (
    f"Fixed weekday {BUSINESS_HOURS_START_UTC:02d}:00-{BUSINESS_HOURS_END_UTC:02d}:00 UTC window - "
    "a v1 simplification, not per-resource timezone detection. There's no reliable timezone signal "
    "in what's synced, so every resource is compared against this same fixed window regardless of "
    "its actual region."
)

RECOMMENDED_SCHEDULE = (
    "Standard template, not a per-resource optimization: power off outside business hours on "
    "weeknights, and power off entirely on weekends. A reasonable starting point to review, not a "
    "precise schedule derived from this specific resource's pattern."
)

_ON_HOURS_PER_WEEK = len(BUSINESS_DAYS) * (BUSINESS_HOURS_END_UTC - BUSINESS_HOURS_START_UTC)
OFF_HOURS_FRACTION_OF_WEEK = (24 * 7 - _ON_HOURS_PER_WEEK) / (24 * 7)


def estimate_monthly_schedule_savings(avg_daily_cost: float | None) -> tuple[float | None, str]:
    if avg_daily_cost is None:
        return None, "No cost data found for this resource in the lookback window; savings can't be estimated."

    savings = avg_daily_cost * 30 * OFF_HOURS_FRACTION_OF_WEEK
    note = (
        "Approximate: current average daily cost over the lookback window x 30, scaled to the "
        f"~{OFF_HOURS_FRACTION_OF_WEEK:.0%} of the week the standard schedule would power the "
        "resource off, assuming cost is roughly uniform per hour while running. Not a billing quote."
    )
    return round(savings, 2), note


def _resource_name(resource: Resource) -> str | None:
    raw_metadata = resource.raw_metadata or {}
    return raw_metadata.get("name")


def build_non_peak_scheduling_recommendations(
    db: Session, cloud_account_id: uuid.UUID | None = None
) -> dict[str, Any]:
    if cloud_account_id is None:
        # Phase 1 is single-subscription, same convention as the other recommendation endpoints.
        cloud_account_id = get_or_create_cloud_account(db, settings.azure_subscription_id).id

    cost_model = LinearBurnRateModel(trailing_window_days=settings.idle_lookback_days)

    # Same resource types as rightsizing - VMs and App Services are the two
    # types a start/stop schedule actually applies to.
    resources = (
        db.query(Resource)
        .filter(Resource.cloud_account_id == cloud_account_id)
        .filter(Resource.resource_type.in_(CPU_METRIC_BY_RESOURCE_TYPE.keys()))
        .all()
    )

    recommendations = []
    for resource in resources:
        tag_result = detect_non_prod_by_tag(resource.tags)
        name_result = detect_non_prod_by_name(_resource_name(resource))

        metric_name = CPU_METRIC_BY_RESOURCE_TYPE[resource.resource_type]
        readings = (
            db.query(UtilizationMetric.timestamp, UtilizationMetric.value)
            .filter_by(resource_id=resource.id, metric_name=metric_name)
            .all()
        )
        usage_result = evaluate_peak_off_peak_usage(
            [(ts, value) for ts, value in readings],
            lookback_days=settings.idle_lookback_days,
            off_peak_ratio_threshold=settings.off_peak_usage_ratio_threshold,
        )

        # Per GOV-001: tag OR name OR usage pattern - any one signal is
        # sufficient, not all required to agree.
        if not (tag_result.matched or name_result.matched or usage_result.is_flagged):
            continue

        daily_costs = get_resource_daily_costs(db, resource.id)
        cost_result = cost_model.forecast(daily_costs, horizon_days=1)
        avg_daily_cost = None if cost_result.insufficient_data else cost_result.daily_rate
        estimated_monthly_savings, savings_note = estimate_monthly_schedule_savings(avg_daily_cost)

        recommendations.append(
            {
                "resource_id": str(resource.id),
                "external_resource_id": resource.external_resource_id,
                "resource_type": resource.resource_type,
                "resource_group": resource.resource_group,
                "region": resource.region,
                "signals": {
                    "tag": {"matched": tag_result.matched, "detail": tag_result.detail},
                    "naming": {"matched": name_result.matched, "detail": name_result.detail},
                    "usage_pattern": {
                        "matched": usage_result.is_flagged,
                        "detail": usage_result.detail,
                        "peak_avg_cpu_percent": (
                            round(usage_result.peak_avg_cpu_percent, 2)
                            if usage_result.peak_avg_cpu_percent is not None
                            else None
                        ),
                        "off_peak_avg_cpu_percent": (
                            round(usage_result.off_peak_avg_cpu_percent, 2)
                            if usage_result.off_peak_avg_cpu_percent is not None
                            else None
                        ),
                    },
                },
                "recommended_schedule": RECOMMENDED_SCHEDULE,
                "estimated_monthly_savings": estimated_monthly_savings,
                "savings_note": savings_note,
            }
        )

    return {
        "idle_lookback_days": settings.idle_lookback_days,
        "off_peak_usage_ratio_threshold": settings.off_peak_usage_ratio_threshold,
        "business_hours_definition": BUSINESS_HOURS_DEFINITION,
        "recommendations": recommendations,
    }
