from datetime import datetime, timezone

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.azure_inventory import map_resource, sync_inventory
from tests.fixtures.azure_resource_graph import STORAGE_ACCOUNT_ROW, VM_ROW


def test_map_resource_vm():
    mapped = map_resource(VM_ROW)

    assert mapped["provider"] == Provider.AZURE
    # Lowercased at write time (Task 18) - Azure resource IDs are canonically
    # case-insensitive but Resource Graph doesn't reliably return the same casing
    # for a given resource across syncs (Task 17's live finding).
    assert mapped["external_resource_id"] == VM_ROW["id"].lower()
    assert mapped["name"] == "vm-web-01"
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
    assert mapped["name"] is None
    assert "created_at" not in mapped
    assert mapped["tags"] == {}


def _fake_fetch(rows):
    def fetch(subscription_id: str):
        return rows

    return fetch


def test_sync_inventory_creates_resources(db_session):
    # Scoped to rows this test creates, not an absolute count - the dev DB this
    # test suite runs against also carries real resources from live-run
    # verification (see README), so a global count() isn't a valid assertion here.
    before = db_session.query(Resource).count()

    summary = sync_inventory(db_session, fetch=_fake_fetch([VM_ROW, STORAGE_ACCOUNT_ROW]))

    assert summary.found == 2
    assert summary.created == 2
    assert summary.updated == 0
    assert db_session.query(Resource).count() == before + 2
    assert (
        db_session.query(Resource)
        .filter(Resource.external_resource_id.in_([VM_ROW["id"].lower(), STORAGE_ACCOUNT_ROW["id"].lower()]))
        .count()
        == 2
    )
    # get_or_create_cloud_account keys off settings.azure_subscription_id, not
    # anything in the fetched rows, so there's exactly one account for it
    # regardless of how many resources are synced.
    assert db_session.query(CloudAccount).filter_by(external_id=settings.azure_subscription_id).count() == 1


def test_sync_inventory_upsert_does_not_duplicate(db_session):
    before = db_session.query(Resource).count()

    sync_inventory(db_session, fetch=_fake_fetch([VM_ROW, STORAGE_ACCOUNT_ROW]))

    updated_vm_row = {**VM_ROW, "tags": {"env": "prod", "owner": "sre-team"}}
    summary = sync_inventory(db_session, fetch=_fake_fetch([updated_vm_row, STORAGE_ACCOUNT_ROW]))

    assert summary.found == 2
    assert summary.created == 0
    assert summary.updated == 2
    assert db_session.query(Resource).count() == before + 2

    vm = (
        db_session.query(Resource)
        .filter_by(external_resource_id=VM_ROW["id"].lower())
        .one()
    )
    assert vm.tags == {"env": "prod", "owner": "sre-team"}


def test_sync_inventory_case_drift_updates_existing_row_not_duplicate(db_session):
    """Regression test for Task 17's live finding: Azure Resource Graph returning
    a previously-synced resource's id in different casing on a later sync must
    update the existing row, not create a second one."""
    before = db_session.query(Resource).count()

    sync_inventory(db_session, fetch=_fake_fetch([VM_ROW]))
    assert db_session.query(Resource).count() == before + 1

    recased_row = {**VM_ROW, "id": VM_ROW["id"].upper()}
    summary = sync_inventory(db_session, fetch=_fake_fetch([recased_row]))

    assert summary.found == 1
    assert summary.created == 0
    assert summary.updated == 1
    assert db_session.query(Resource).count() == before + 1

    resource = db_session.query(Resource).filter_by(external_resource_id=VM_ROW["id"].lower()).one()
    assert resource.external_resource_id == VM_ROW["id"].lower()
