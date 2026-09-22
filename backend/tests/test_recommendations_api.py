"""Endpoint-level dispatch tests for /api/v1/recommendations/* - specifically
the reserved-instances merge logic (Task 21 item 2). No existing test exercised
this endpoint's dispatch before (the pre-existing reserved-instances tests only
call the service functions directly), so both the "AWS unconfigured" case and
the new "both providers merged" case are new here.

The reserved-instances endpoint is a live pass-through to each provider's own
recommendation engine (see reserved_instances.py's own docstring) - there's no
DB-seeded data to drive it the way the other three categories' endpoint tests
work. Monkeypatching the module-level function references the endpoint calls
(as imported into app.api.recommendations' own namespace) is the standard,
precise way to test its dispatch logic without live Azure/AWS credentials."""

import app.api.recommendations as recommendations_api
from app.core.config import settings

AZURE_NOTE = "Azure field names unverified against real populated data."
AWS_NOTE = "AWS field names unverified against real populated data."


def _fake_azure_result(items=None):
    # `items is None` (not falsy) distinguishes "use the default" from a
    # deliberately empty list - `[] or default` would silently fall back to
    # the default too, since an empty list is falsy in Python.
    return {
        "provider": "azure",
        "source": "Azure Microsoft.Consumption reservationRecommendations API",
        "field_mapping_note": AZURE_NOTE,
        "recommendations": items if items is not None else [{"id": "azure-1", "sku": "Standard_D2s_v3"}],
    }


def _fake_aws_result(items=None):
    return {
        "provider": "aws",
        "source": "AWS Cost Explorer APIs",
        "field_mapping_note": AWS_NOTE,
        "recommendations": (
            items if items is not None else [{"recommendation_type": "reserved_instance", "instance_type": "m5.large"}]
        ),
    }


def test_field_mapping_note_stays_a_plain_string_when_aws_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "")
    monkeypatch.setattr(settings, "aws_region", "")
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    monkeypatch.setattr(recommendations_api, "build_reservation_recommendations", _fake_azure_result)

    response = client.get("/api/v1/recommendations/reserved-instances")

    assert response.status_code == 200
    body = response.json()
    # Unchanged shape - a plain string, exactly what build_reservation_recommendations
    # returned, not touched by the merge logic at all since AWS never runs.
    assert body["field_mapping_note"] == AZURE_NOTE
    assert isinstance(body["field_mapping_note"], str)
    assert len(body["recommendations"]) == 1


def test_field_mapping_note_becomes_a_dict_with_both_providers_when_both_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "999988887777")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")
    monkeypatch.setattr(recommendations_api, "build_reservation_recommendations", _fake_azure_result)
    monkeypatch.setattr(recommendations_api, "build_aws_reservation_recommendations", _fake_aws_result)

    response = client.get("/api/v1/recommendations/reserved-instances")

    assert response.status_code == 200
    body = response.json()
    # Task 21 fix: both providers' own notes are now present and distinguishable,
    # not just Azure's silently standing in for both.
    assert body["field_mapping_note"] == {"azure": AZURE_NOTE, "aws": AWS_NOTE}
    assert len(body["recommendations"]) == 2
    ids_or_types = {r.get("id") or r.get("recommendation_type") for r in body["recommendations"]}
    assert ids_or_types == {"azure-1", "reserved_instance"}


def test_field_mapping_note_still_a_dict_even_when_aws_has_no_items(client, monkeypatch):
    # Per this task's chosen trigger: keyed on aws_configured, not on whether
    # this particular call happened to find any AWS items - flagged reasoning
    # in results.txt. AWS's own note is still meaningful even with zero items
    # this time (it's a caveat about mapping trustworthiness in general).
    monkeypatch.setattr(settings, "aws_account_id", "999988887777")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")
    monkeypatch.setattr(recommendations_api, "build_reservation_recommendations", _fake_azure_result)
    monkeypatch.setattr(recommendations_api, "build_aws_reservation_recommendations", lambda: _fake_aws_result(items=[]))

    response = client.get("/api/v1/recommendations/reserved-instances")

    body = response.json()
    assert body["field_mapping_note"] == {"azure": AZURE_NOTE, "aws": AWS_NOTE}
    assert len(body["recommendations"]) == 1  # only Azure's one item
