from datetime import date, timedelta

from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.forecast import build_forecast


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AZURE, external_id=external_id, display_name="Forecast Test Sub")
    db_session.add(account)
    db_session.flush()
    return account


def _add_cost(db_session, account, resource, day, amount, charge_type="Usage"):
    db_session.add(
        CostRecord(
            cloud_account_id=account.id,
            resource_id=resource.id if resource else None,
            date=day,
            amortized_cost=amount,
            currency="USD",
            granularity="Daily",
            charge_type=charge_type,
        )
    )


# --- build_forecast: precise math against isolated, seeded data -----------------
# These use their own dedicated cloud_account_id, not the real subscription's
# account, so they aren't affected by the 237 real cost_records Task 6's live
# run already put in this dev DB.


def test_build_forecast_aggregate_no_filters(db_session):
    account = _seed_account(db_session, "test-sub-forecast-aggregate")
    vm = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="vm-1",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-a",
        tags={},
        raw_metadata={},
    )
    db_session.add(vm)
    db_session.flush()

    base = date(2026, 9, 1)
    for offset, amount in enumerate([10.0, 10.0, 10.0]):
        _add_cost(db_session, account, vm, base + timedelta(days=offset), amount)
    db_session.commit()

    result = build_forecast(db_session, horizon_days=7, cloud_account_id=account.id)

    assert result["insufficient_data"] is False
    assert result["daily_rate"] == 10.0
    assert result["horizon_days"] == 7
    assert len(result["series"]) == 7
    assert result["series"][0]["date"] == "2026-09-04"
    assert result["rollups"] == {7: 70.0}


def test_build_forecast_resource_group_filter_excludes_other_groups(db_session):
    account = _seed_account(db_session, "test-sub-forecast-rg")
    vm_a = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="vm-a",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-a",
        tags={},
        raw_metadata={},
    )
    vm_b = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="vm-b",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-b",
        tags={},
        raw_metadata={},
    )
    db_session.add_all([vm_a, vm_b])
    db_session.flush()

    base = date(2026, 9, 1)
    _add_cost(db_session, account, vm_a, base, 5.0)
    _add_cost(db_session, account, vm_b, base, 100.0)
    db_session.commit()

    result = build_forecast(db_session, horizon_days=1, resource_group="rg-a", cloud_account_id=account.id)

    assert result["daily_rate"] == 5.0


def test_build_forecast_resource_id_filter_excludes_other_resources(db_session):
    account = _seed_account(db_session, "test-sub-forecast-resource-id")
    vm_a = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="vm-a",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-a",
        tags={},
        raw_metadata={},
    )
    vm_b = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="vm-b",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg-a",  # same group as vm_a - resource_id must narrow further than resource_group alone
        tags={},
        raw_metadata={},
    )
    db_session.add_all([vm_a, vm_b])
    db_session.flush()

    base = date(2026, 9, 1)
    _add_cost(db_session, account, vm_a, base, 5.0)
    _add_cost(db_session, account, vm_b, base, 100.0)
    db_session.commit()

    result = build_forecast(db_session, horizon_days=1, resource_id=vm_a.id, cloud_account_id=account.id)

    assert result["daily_rate"] == 5.0


def test_build_forecast_rollups_cap_to_horizon_and_include_horizon_itself(db_session):
    account = _seed_account(db_session, "test-sub-forecast-rollups")
    base = date(2026, 9, 1)
    _add_cost(db_session, account, None, base, 10.0)
    db_session.commit()

    result = build_forecast(db_session, horizon_days=10, cloud_account_id=account.id)

    # horizon_days=10 doesn't reach the 30 or 90-day standard windows, so only
    # the 7-day rollup applies plus horizon_days itself (10).
    assert result["rollups"] == {7: 70.0, 10: 100.0}


def test_build_forecast_partial_window_uses_available_history(db_session):
    account = _seed_account(db_session, "test-sub-forecast-partial")
    base = date(2026, 9, 1)
    _add_cost(db_session, account, None, base, 20.0)
    _add_cost(db_session, account, None, base + timedelta(days=1), 40.0)
    db_session.commit()

    result = build_forecast(db_session, horizon_days=1, cloud_account_id=account.id)

    assert result["daily_rate"] == 30.0  # average of both available days
    assert result["insufficient_data"] is False


def test_build_forecast_zero_data_returns_insufficient_data(db_session):
    account = _seed_account(db_session, "test-sub-forecast-empty")
    db_session.commit()

    result = build_forecast(db_session, horizon_days=90, cloud_account_id=account.id)

    assert result["insufficient_data"] is True
    assert result["daily_rate"] is None
    assert result["series"] == []
    assert result["rollups"] == {}


# --- HTTP-level endpoint tests ---------------------------------------------------
# The endpoint has no cloud_account_id query param (Phase 1 is single-subscription,
# per the task's fixed param list), so it always resolves to the real configured
# subscription's account - which already has 237 real cost_records from Task 6's
# live run. These assert wiring/shape correctness against that real data rather
# than precise values (which would drift if the live data is re-synced) - the
# precise math is already covered above against isolated fixtures.


def test_forecast_endpoint_aggregate(client):
    response = client.get("/api/v1/forecast", params={"horizon_days": 30})

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is False
    assert body["daily_rate"] > 0
    assert len(body["series"]) == 30
    assert set(body["rollups"].keys()) == {"7", "30"}


def test_forecast_endpoint_resource_type_filter(client):
    response = client.get(
        "/api/v1/forecast",
        params={"horizon_days": 7, "resource_type": "microsoft.compute/virtualmachines"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is False
    assert body["daily_rate"] > 0


def test_forecast_endpoint_resource_id_filter(client):
    # nise-rg's VM (nise-dev) is a real resource with real cost history in the
    # live subscription (Task 15's own findings) - use its actual resource_id
    # from the inventory endpoint rather than hardcoding one.
    resources = client.get("/api/v1/inventory", params={"resource_group": "nise-rg"}).json()["resources"]
    vm = next(r for r in resources if r["resource_type"] == "microsoft.compute/virtualmachines")

    response = client.get(
        "/api/v1/forecast",
        params={"horizon_days": 7, "resource_id": vm["resource_id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is False
    assert body["daily_rate"] > 0

    # A resource_id filter must narrow strictly further than an unfiltered
    # forecast - the VM alone shouldn't out-earn the whole subscription's rate.
    aggregate = client.get("/api/v1/forecast", params={"horizon_days": 7}).json()
    assert body["daily_rate"] <= aggregate["daily_rate"]


def test_forecast_endpoint_unknown_resource_id_returns_insufficient_data(client):
    response = client.get(
        "/api/v1/forecast",
        params={"horizon_days": 7, "resource_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_data"] is True
