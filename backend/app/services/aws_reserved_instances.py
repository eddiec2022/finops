from typing import Any, Callable

import boto3

from app.core.config import settings

# GOV-002 2.5: AWS Cost Explorer's own native recommendation APIs, direct
# analogue of the Azure Consumption reservationRecommendations API Task 12
# built against - same "thin, on-demand pass-through to the provider's own
# engine, not computed locally" shape as reserved_instances.py. Unlike Azure's
# single API, AWS splits this into two: Reserved Instances (classic, per-
# instance-family commitment) and Savings Plans (newer, dollar-commitment
# across a broader usage category) - both are genuinely "the 4th
# recommendation category" per GOV-002 2.5, so both are called and merged into
# one response here, mirroring how this task's item 5 wants AWS results merged
# into the same existing /recommendations/reserved-instances endpoint.

RESERVATION_LOOKBACK_PERIOD = "THIRTY_DAYS"
RESERVATION_TERM = "ONE_YEAR"
RESERVATION_PAYMENT_OPTION = "NO_UPFRONT"
# EC2 is the only compute type this app's AWS connector covers so far (Task 19/20) -
# matches the same "don't cover every AWS service" scoping as the rest of Phase 2.
RESERVATION_SERVICE = "Amazon Elastic Compute Cloud - Compute"

SAVINGS_PLAN_TYPE = "COMPUTE_SP"
SAVINGS_PLAN_LOOKBACK_PERIOD = "THIRTY_DAYS"
SAVINGS_PLAN_TERM = "ONE_YEAR"
SAVINGS_PLAN_PAYMENT_OPTION = "NO_UPFRONT"


def _client() -> Any:
    session = boto3.Session(
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
    return session.client("ce")


def fetch_reservation_recommendations() -> list[dict[str, Any]]:
    """Call GetReservationPurchaseRecommendation live - a real prerequisite
    worth stating plainly: AWS's own docs describe this as requiring a
    meaningful, consistent amount of On-Demand usage history (informally,
    "several weeks") before it produces anything - a real analogue of Azure's
    own "this subscription's usage history hasn't produced a recommendation
    yet" empty-result case Task 12 found, not a bug if it comes back empty
    against a new/low-usage account."""
    response = _client().get_reservation_purchase_recommendation(
        Service=RESERVATION_SERVICE,
        LookbackPeriodInDays=RESERVATION_LOOKBACK_PERIOD,
        TermInYears=RESERVATION_TERM,
        PaymentOption=RESERVATION_PAYMENT_OPTION,
    )
    recommendations = []
    for group in response.get("Recommendations", []):
        for detail in group.get("RecommendationDetails", []):
            recommendations.append({**detail, "_group": {k: v for k, v in group.items() if k != "RecommendationDetails"}})
    return recommendations


def fetch_savings_plans_recommendations() -> list[dict[str, Any]]:
    """Call GetSavingsPlansPurchaseRecommendation live - same real usage-
    history prerequisite as GetReservationPurchaseRecommendation above."""
    response = _client().get_savings_plans_purchase_recommendation(
        SavingsPlansType=SAVINGS_PLAN_TYPE,
        TermInYears=SAVINGS_PLAN_TERM,
        PaymentOption=SAVINGS_PLAN_PAYMENT_OPTION,
        LookbackPeriodInDays=SAVINGS_PLAN_LOOKBACK_PERIOD,
    )
    top = response.get("SavingsPlansPurchaseRecommendation") or {}
    return list(top.get("SavingsPlansPurchaseRecommendationDetails", []))


# Field-mapping note, same convention as reserved_instances.FIELD_MAPPING_NOTE:
# these field names are taken from AWS's documented response schema, not
# verified against a real populated response (see results.txt for what moto
# could and couldn't simulate, and what's genuinely unverifiable until Task 21
# has real usage history). The full raw API item is preserved under `raw` on
# every mapped recommendation so nothing is lost if a mapped name is wrong.
FIELD_MAPPING_NOTE = (
    "Field names are mapped per AWS's documented schema for these two APIs, not verified against a "
    "real populated response - this app has no AWS account with real usage history yet (see Task 20 "
    "investigation notes). Each recommendation's full raw API response is included under `raw` so "
    "nothing is lost if a mapped field name is wrong."
)


def map_reservation_recommendation(detail: dict[str, Any]) -> dict[str, Any]:
    ec2_details = ((detail.get("InstanceDetails") or {}).get("EC2InstanceDetails")) or {}
    return {
        "recommendation_type": "reserved_instance",
        "instance_type": ec2_details.get("InstanceType"),
        "region": ec2_details.get("Region"),
        "recommended_quantity": detail.get("RecommendedNumberOfInstancesToPurchase"),
        "estimated_monthly_savings": detail.get("EstimatedMonthlySavingsAmount"),
        "estimated_monthly_savings_percentage": detail.get("EstimatedMonthlySavingsPercentage"),
        "currency": detail.get("CurrencyCode"),
        "term": RESERVATION_TERM,
        "payment_option": RESERVATION_PAYMENT_OPTION,
        "raw": detail,
    }


def map_savings_plan_recommendation(detail: dict[str, Any]) -> dict[str, Any]:
    plan_details = detail.get("SavingsPlansDetails") or {}
    return {
        "recommendation_type": "savings_plan",
        "instance_family": plan_details.get("InstanceFamily"),
        "region": plan_details.get("Region"),
        "hourly_commitment": detail.get("HourlyCommitmentToPurchase"),
        "estimated_monthly_savings": detail.get("EstimatedMonthlySavingsAmount"),
        "estimated_savings_percentage": detail.get("EstimatedSavingsPercentage"),
        "currency": detail.get("CurrencyCode"),
        "term": SAVINGS_PLAN_TERM,
        "payment_option": SAVINGS_PLAN_PAYMENT_OPTION,
        "raw": detail,
    }


def build_aws_reservation_recommendations(
    fetch_reservations: Callable[[], list[dict[str, Any]]] = fetch_reservation_recommendations,
    fetch_savings_plans: Callable[[], list[dict[str, Any]]] = fetch_savings_plans_recommendations,
) -> dict[str, Any]:
    reservation_items = [map_reservation_recommendation(d) for d in fetch_reservations()]
    savings_plan_items = [map_savings_plan_recommendation(d) for d in fetch_savings_plans()]
    return {
        "provider": "aws",
        "source": (
            "AWS Cost Explorer GetReservationPurchaseRecommendation + "
            "GetSavingsPlansPurchaseRecommendation APIs (live calls, not computed locally)"
        ),
        "field_mapping_note": FIELD_MAPPING_NOTE,
        "recommendations": reservation_items + savings_plan_items,
    }
