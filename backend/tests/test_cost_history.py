from datetime import date, timedelta

from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.forecast import build_daily_cost_history


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AZURE, external_id=external_id, display_name="Cost History Test Sub")
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


def test_build_daily_cost_history_aggregate_no_filters(db_session):
    account = _seed_account(db_session, "test-sub-cost-history-aggregate")
    base = date(2026, 9, 1)
    _add_cost(db_session, account, None, base, 10.0)
    _add_cost(db_session, account, None, base + timedelta(days=1), 15.0)
    db_session.commit()

    result = build_daily_cost_history(db_session, cloud_account_id=account.id)

    assert result["series"] == [
        {"date": "2026-09-01", "actual_cost": 10.0},
        {"date": "2026-09-02", "actual_cost": 15.0},
    ]


def test_build_daily_cost_history_resource_group_filter_excludes_other_groups(db_session):
    account = _seed_account(db_session, "test-sub-cost-history-rg")
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

    result = build_daily_cost_history(db_session, resource_group="rg-a", cloud_account_id=account.id)

    assert result["series"] == [{"date": "2026-09-01", "actual_cost": 5.0}]


def test_build_daily_cost_history_resource_id_filter_excludes_other_resources(db_session):
    account = _seed_account(db_session, "test-sub-cost-history-resource-id")
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
        resource_group="rg-a",
        tags={},
        raw_metadata={},
    )
    db_session.add_all([vm_a, vm_b])
    db_session.flush()

    base = date(2026, 9, 1)
    _add_cost(db_session, account, vm_a, base, 5.0)
    _add_cost(db_session, account, vm_b, base, 100.0)
    db_session.commit()

    result = build_daily_cost_history(db_session, resource_id=vm_a.id, cloud_account_id=account.id)

    assert result["series"] == [{"date": "2026-09-01", "actual_cost": 5.0}]


def test_build_daily_cost_history_no_data_returns_empty_series(db_session):
    account = _seed_account(db_session, "test-sub-cost-history-empty")
    db_session.commit()

    result = build_daily_cost_history(db_session, cloud_account_id=account.id)

    assert result["series"] == []


def test_cost_history_endpoint_aggregate(client):
    response = client.get("/api/v1/cost")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["series"], list)
    # The real configured subscription already has 237 real cost_records
    # (Task 6's live run) - assert wiring/shape correctness against that real
    # data rather than precise values, same principle as the forecast endpoint
    # tests.
    assert len(body["series"]) > 0
    first = body["series"][0]
    assert set(first.keys()) == {"date", "actual_cost"}


def test_cost_history_endpoint_resource_type_filter(client):
    response = client.get(
        "/api/v1/cost",
        params={"resource_type": "microsoft.compute/virtualmachines"},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["series"], list)


def test_cost_history_endpoint_resource_id_filter(client):
    resources = client.get("/api/v1/inventory", params={"resource_group": "nise-rg"}).json()["resources"]
    vm = next(r for r in resources if r["resource_type"] == "microsoft.compute/virtualmachines")

    response = client.get("/api/v1/cost", params={"resource_id": vm["resource_id"]})

    assert response.status_code == 200
    body = response.json()
    assert len(body["series"]) > 0
    total_for_vm = sum(point["actual_cost"] for point in body["series"])

    aggregate = client.get("/api/v1/cost").json()
    total_aggregate = sum(point["actual_cost"] for point in aggregate["series"])
    assert total_for_vm <= total_aggregate
