from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.inventory_listing import build_resource_list


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AZURE, external_id=external_id, display_name="Inventory Listing Test Sub")
    db_session.add(account)
    db_session.flush()
    return account


def _add_resource(db_session, account, external_id, resource_group, resource_type, name, region="eastus"):
    resource = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id=external_id,
        name=name,
        resource_type=resource_type,
        region=region,
        resource_group=resource_group,
        tags={},
        raw_metadata={"name": name},
    )
    db_session.add(resource)
    return resource


def test_build_resource_list_returns_all_resources_for_account(db_session):
    account = _seed_account(db_session, "test-sub-inventory-listing-all")
    _add_resource(db_session, account, "vm-a", "rg-a", "microsoft.compute/virtualmachines", "vm-web-01")
    _add_resource(db_session, account, "st-a", "rg-a", "microsoft.storage/storageaccounts", "stlogs01")
    db_session.commit()

    result = build_resource_list(db_session, cloud_account_id=account.id)

    assert len(result["resources"]) == 2
    names = {r["name"] for r in result["resources"]}
    assert names == {"vm-web-01", "stlogs01"}
    first = result["resources"][0]
    assert set(first.keys()) == {"resource_id", "external_resource_id", "name", "resource_group", "resource_type", "region"}


def test_build_resource_list_resource_group_filter_excludes_other_groups(db_session):
    account = _seed_account(db_session, "test-sub-inventory-listing-rg")
    _add_resource(db_session, account, "vm-a", "rg-a", "microsoft.compute/virtualmachines", "vm-web-01")
    _add_resource(db_session, account, "vm-b", "rg-b", "microsoft.compute/virtualmachines", "vm-web-02")
    db_session.commit()

    result = build_resource_list(db_session, resource_group="rg-a", cloud_account_id=account.id)

    assert len(result["resources"]) == 1
    assert result["resources"][0]["external_resource_id"] == "vm-a"


def test_build_resource_list_no_resources_returns_empty_list(db_session):
    account = _seed_account(db_session, "test-sub-inventory-listing-empty")
    db_session.commit()

    result = build_resource_list(db_session, cloud_account_id=account.id)

    assert result["resources"] == []


def test_build_resource_list_missing_name_returns_none(db_session):
    account = _seed_account(db_session, "test-sub-inventory-listing-noname")
    resource = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="vm-noname",
        name=None,
        resource_type="microsoft.compute/virtualmachines",
        region="eastus",
        resource_group="rg-a",
        tags={},
        raw_metadata={},
    )
    db_session.add(resource)
    db_session.commit()

    result = build_resource_list(db_session, cloud_account_id=account.id)

    assert result["resources"][0]["name"] is None


def test_inventory_endpoint_aggregate(client):
    response = client.get("/api/v1/inventory")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["resources"], list)
    # The real configured subscription already has synced resources (Task 2's
    # live sync) - assert wiring/shape correctness against that real data,
    # same principle as the cost history endpoint tests.
    assert len(body["resources"]) > 0
    first = body["resources"][0]
    assert set(first.keys()) == {"resource_id", "external_resource_id", "name", "resource_group", "resource_type", "region"}


def test_inventory_endpoint_resource_group_filter(client):
    all_resources = client.get("/api/v1/inventory").json()["resources"]
    some_group = next((r["resource_group"] for r in all_resources if r["resource_group"]), None)
    assert some_group is not None, "expected at least one resource with a resource_group in the live subscription"

    response = client.get("/api/v1/inventory", params={"resource_group": some_group})

    assert response.status_code == 200
    body = response.json()
    assert len(body["resources"]) > 0
    assert all(r["resource_group"] == some_group for r in body["resources"])
