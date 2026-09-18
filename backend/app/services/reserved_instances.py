from typing import Any, Callable

import httpx
from azure.identity import ClientSecretCredential

from app.core.config import settings

# The most recent API version confirmed working against the real subscription
# during Task 12's Phase 1 investigation (200 OK, empty result set - this
# dev subscription's usage history is too short/gappy for Azure's own engine
# to have produced a recommendation yet, matching everything Tasks 9-11 found
# about this environment). 2023-05-01 and 2021-10-01 were also confirmed
# working; 2024-08-01 is used as the current one.
API_VERSION = "2024-08-01"

# A cold first call to management.azure.com timed out at 30s during Phase 1
# investigation but succeeded immediately on retry with a longer timeout -
# looked like one-off connection setup latency, not something specific to
# this endpoint, but the timeout here is set generously to absorb that rather
# than fail a request over normal network variance.
REQUEST_TIMEOUT_SECONDS = 60.0


def fetch_reservation_recommendations(subscription_id: str) -> list[dict[str, Any]]:
    """Call Azure's own Microsoft.Consumption reservationRecommendations API live.

    Unlike the other three recommendation endpoints (rightsizing, idle
    resources, non-peak scheduling), which are compute-on-read against data
    already synced into this app's own DB, there is nothing to sync or
    compute locally here - Azure runs this analysis itself from its own
    internal usage history, which this app doesn't have (or need) a local
    copy of. This is a thin, on-demand pass-through to Azure's engine, called
    live on every request to this endpoint, not a DB read.

    Raw REST via httpx + azure-identity (both already dependencies), not the
    azure-mgmt-consumption SDK - Phase 1 investigation validated this exact
    call shape against the real subscription and it's a single GET with no
    complex request body, so adding a new SDK dependency for it wasn't
    justified.
    """
    credential = ClientSecretCredential(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    token = credential.get_token("https://management.azure.com/.default").token
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.Consumption/reservationRecommendations"
        f"?api-version={API_VERSION}"
    )
    response = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json().get("value", [])


# Field-mapping note, surfaced both here and in the endpoint's response:
# these names are taken from Microsoft's documented schema for this API, NOT
# verified against a real populated response the way Tasks 9/10 verified
# their field-name assumptions against real synced data - Phase 1's live call
# returned an empty result set (this subscription genuinely has no
# recommendations to give yet), so there was nothing populated to check
# field names against. The full raw API item is preserved under `raw` on
# every mapped recommendation specifically so nothing is lost if a mapped
# field name here turns out to be wrong once real data exists.
FIELD_MAPPING_NOTE = (
    "Field names are mapped per Microsoft's documented schema for this API, not verified against a "
    "real populated response - this subscription's usage history hasn't produced any recommendations "
    "yet to check field names against (see Task 12 investigation notes). Each recommendation's full "
    "raw API response is included under `raw` so nothing is lost if a mapped field name is wrong."
)


def map_recommendation(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Azure reservationRecommendations item into a shape
    roughly consistent with the other recommendation endpoints (resource/
    scope identified, a basis, an estimated savings figure) - without forcing
    fields Azure's response doesn't naturally have into that shape. The
    `raw` field is the actual source of truth; everything else here is a
    best-effort, unverified convenience mapping (see FIELD_MAPPING_NOTE).
    """
    properties = item.get("properties") or {}
    return {
        "id": item.get("id"),
        "sku": item.get("sku"),
        "location": item.get("location"),
        "resource_type": properties.get("resourceType"),
        "scope": properties.get("scope"),
        "term": properties.get("term"),
        "look_back_period": properties.get("lookBackPeriod"),
        "recommended_quantity": properties.get("recommendedQuantity"),
        "cost_with_no_reserved_instances": properties.get("costWithNoReservedInstances"),
        "total_cost_with_reserved_instances": properties.get("totalCostWithReservedInstances"),
        "estimated_monthly_savings": properties.get("netSavings"),
        "currency": properties.get("currency"),
        "raw": item,
    }


def build_reservation_recommendations(
    fetch: Callable[[str], list[dict[str, Any]]] = fetch_reservation_recommendations,
) -> dict[str, Any]:
    subscription_id = settings.azure_subscription_id
    raw_items = fetch(subscription_id)
    return {
        "source": "Azure Microsoft.Consumption reservationRecommendations API (live call, not computed locally)",
        "field_mapping_note": FIELD_MAPPING_NOTE,
        "recommendations": [map_recommendation(item) for item in raw_items],
    }
