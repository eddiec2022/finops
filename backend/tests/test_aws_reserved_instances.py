from app.services.aws_reserved_instances import (
    build_aws_reservation_recommendations,
    map_reservation_recommendation,
    map_savings_plan_recommendation,
)

RESERVATION_DETAIL = {
    "AccountId": "999988887777",
    "InstanceDetails": {
        "EC2InstanceDetails": {
            "Family": "m5",
            "InstanceType": "m5.large",
            "Region": "us-east-1",
            "Platform": "Linux/UNIX",
            "Tenancy": "default",
        }
    },
    "RecommendedNumberOfInstancesToPurchase": "2",
    "EstimatedMonthlySavingsAmount": "30.00",
    "EstimatedMonthlySavingsPercentage": "20.0",
    "CurrencyCode": "USD",
}

SAVINGS_PLAN_DETAIL = {
    "SavingsPlansDetails": {"Region": "us-east-1", "InstanceFamily": "m5", "OfferingId": "abc-123"},
    "HourlyCommitmentToPurchase": "0.05",
    "EstimatedMonthlySavingsAmount": "18.00",
    "EstimatedSavingsPercentage": "15.0",
    "CurrencyCode": "USD",
}


def test_map_reservation_recommendation_extracts_documented_fields():
    mapped = map_reservation_recommendation(RESERVATION_DETAIL)

    assert mapped["recommendation_type"] == "reserved_instance"
    assert mapped["instance_type"] == "m5.large"
    assert mapped["region"] == "us-east-1"
    assert mapped["recommended_quantity"] == "2"
    assert mapped["estimated_monthly_savings"] == "30.00"
    assert mapped["currency"] == "USD"
    assert mapped["raw"] == RESERVATION_DETAIL


def test_map_reservation_recommendation_missing_fields_does_not_crash():
    mapped = map_reservation_recommendation({"AccountId": "x"})

    assert mapped["instance_type"] is None
    assert mapped["estimated_monthly_savings"] is None
    assert mapped["raw"] == {"AccountId": "x"}


def test_map_savings_plan_recommendation_extracts_documented_fields():
    mapped = map_savings_plan_recommendation(SAVINGS_PLAN_DETAIL)

    assert mapped["recommendation_type"] == "savings_plan"
    assert mapped["instance_family"] == "m5"
    assert mapped["region"] == "us-east-1"
    assert mapped["hourly_commitment"] == "0.05"
    assert mapped["estimated_monthly_savings"] == "18.00"
    assert mapped["raw"] == SAVINGS_PLAN_DETAIL


def test_build_aws_reservation_recommendations_merges_both_apis():
    result = build_aws_reservation_recommendations(
        fetch_reservations=lambda: [RESERVATION_DETAIL],
        fetch_savings_plans=lambda: [SAVINGS_PLAN_DETAIL],
    )

    assert result["provider"] == "aws"
    assert len(result["recommendations"]) == 2
    types = {r["recommendation_type"] for r in result["recommendations"]}
    assert types == {"reserved_instance", "savings_plan"}
    assert "not computed locally" in result["source"].lower()
    assert "not verified" in result["field_mapping_note"].lower()


def test_build_aws_reservation_recommendations_empty_result_is_not_an_error():
    # The real, expected shape against an account without enough usage
    # history for either API to have produced anything yet - same "empty
    # result, not a failure" principle Task 12 found for Azure.
    result = build_aws_reservation_recommendations(fetch_reservations=lambda: [], fetch_savings_plans=lambda: [])

    assert result["recommendations"] == []
