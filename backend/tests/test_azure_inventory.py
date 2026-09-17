from datetime import datetime, timezone

from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.azure_inventory import map_resource, sync_inventory
from tests.fixtures.azure_resource_graph import STORAGE_ACCOUNT_ROW, VM_ROW


def test_map_resource_vm():
    mapped = map_resource(VM_ROW)

    assert mapped["provider"] == Provider.AZURE
    assert mapped["external_resource_id"] == VM_ROW["id"]
    assert mapped["resource_type"] == "microsoft.compute/virtualmachines"
    assert mapped["region"] == "eastus"
    assert mapped["resource_group"] == "rg-prod"
    assert mapped["tags"] == {"env": "prod", "owner": "platform-team"}
    assert mapped["sku"] == "Standard_D2s_v3"
    assert mapped["created_at"] == datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert mapped["raw_metadata"] == VM_ROW


def test_map_resource_storage_account():
    mapped = map_resource(STORAGE_ACCOUNT_ROW)

    assert mapped["resource_type"] == "microsoft.storage/storageaccounts"
    assert mapped["sku"] == "Standard_LRS"
    assert mapped["tags"] == {"env": "prod"}
    assert mapped["created_at"] == datetime(2024, 11, 2, 9, 30, 0, tzinfo=timezone.utc)


def test_map_resource_missing_created_at_and_sku():
    row = {
        "id": "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Network/publicIPAddresses/pip-1",
        "type": "microsoft.network/publicipaddresses",
        "location": "westus",
        "resourceGroup": "rg",
        "tags": None,
        "sku": None,
        "properties": {},
    }

    mapped = map_resource(row)

    assert mapped["sku"] is None
    assert "created_at" not in mapped
    assert mapped["tags"] == {}


def _fake_fetch(rows):
    def fetch(subscription_id: str):
        return rows

    return fetch


def test_sync_inventory_creates_resources(db_session):
    summary = sync_inventory(db_session, fetch=_fake_fetch([VM_ROW, STORAGE_ACCOUNT_ROW]))

    assert summary.found == 2
    assert summary.created == 2
    assert summary.updated == 0
    assert db_session.query(Resource).count() == 2
    assert db_session.query(CloudAccount).count() == 1


def test_sync_inventory_upsert_does_not_duplicate(db_session):
    sync_inventory(db_session, fetch=_fake_fetch([VM_ROW, STORAGE_ACCOUNT_ROW]))

    updated_vm_row = {**VM_ROW, "tags": {"env": "prod", "owner": "sre-team"}}
    summary = sync_inventory(db_session, fetch=_fake_fetch([updated_vm_row, STORAGE_ACCOUNT_ROW]))

    assert summary.found == 2
    assert summary.created == 0
    assert summary.updated == 2
    assert db_session.query(Resource).count() == 2
    assert db_session.query(CloudAccount).count() == 1

    vm = (
        db_session.query(Resource)
        .filter_by(external_resource_id=VM_ROW["id"])
        .one()
    )
    assert vm.tags == {"env": "prod", "owner": "sre-team"}
