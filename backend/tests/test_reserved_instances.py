from app.services.reserved_instances import build_reservation_recommendations, map_recommendation

RAW_ITEM = {
    "id": "/subscriptions/.../providers/Microsoft.Consumption/reservationRecommendations/abc123",
    "sku": "Standard_D2s_v3",
    "location": "eastus",
    "properties": {
        "resourceType": "VirtualMachines",
        "scope": "Single",
        "term": "P1Y",
        "lookBackPeriod": "Last30Days",
        "recommendedQuantity": 2,
        "costWithNoReservedInstances": 500.0,
        "totalCostWithReservedInstances": 320.0,
        "netSavings": 180.0,
        "currency": "USD",
    },
}


def test_map_recommendation_extracts_documented_fields():
    mapped = map_recommendation(RAW_ITEM)

    assert mapped["sku"] == "Standard_D2s_v3"
    assert mapped["location"] == "eastus"
    assert mapped["resource_type"] == "VirtualMachines"
    assert mapped["scope"] == "Single"
    assert mapped["term"] == "P1Y"
    assert mapped["look_back_period"] == "Last30Days"
    assert mapped["recommended_quantity"] == 2
    assert mapped["cost_with_no_reserved_instances"] == 500.0
    assert mapped["total_cost_with_reserved_instances"] == 320.0
    assert mapped["estimated_monthly_savings"] == 180.0
    assert mapped["currency"] == "USD"


def test_map_recommendation_preserves_full_raw_item():
    # The raw item is kept verbatim specifically because the field mapping
    # itself is unverified against real populated data (see
    # FIELD_MAPPING_NOTE) - nothing should be lost if a mapped name is wrong.
    mapped = map_recommendation(RAW_ITEM)

    assert mapped["raw"] == RAW_ITEM


def test_map_recommendation_missing_properties_does_not_crash():
    mapped = map_recommendation({"id": "x", "sku": "Standard_D2s_v3"})

    assert mapped["resource_type"] is None
    assert mapped["estimated_monthly_savings"] is None
    assert mapped["raw"] == {"id": "x", "sku": "Standard_D2s_v3"}


def test_build_reservation_recommendations_maps_every_item():
    def fake_fetch(subscription_id):
        return [RAW_ITEM, {**RAW_ITEM, "sku": "Standard_D4s_v3"}]

    result = build_reservation_recommendations(fetch=fake_fetch)

    assert len(result["recommendations"]) == 2
    assert result["recommendations"][0]["sku"] == "Standard_D2s_v3"
    assert result["recommendations"][1]["sku"] == "Standard_D4s_v3"
    assert "not computed locally" in result["source"].lower()
    assert "not verified" in result["field_mapping_note"].lower()


def test_build_reservation_recommendations_empty_result_is_not_an_error():
    # This is the actual shape of the real subscription's live response
    # (Task 12 Phase 1 investigation): a successful call, zero items, because
    # the subscription's usage history hasn't produced a recommendation yet -
    # not a failure case.
    def fake_fetch(subscription_id):
        return []

    result = build_reservation_recommendations(fetch=fake_fetch)

    assert result["recommendations"] == []


def test_build_reservation_recommendations_passes_configured_subscription_id():
    from app.core.config import settings

    seen_subscription_ids = []

    def fake_fetch(subscription_id):
        seen_subscription_ids.append(subscription_id)
        return []

    build_reservation_recommendations(fetch=fake_fetch)

    assert seen_subscription_ids == [settings.azure_subscription_id]
