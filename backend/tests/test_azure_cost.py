from datetime import date

from app.core.config import settings
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.azure_cost import map_cost_response, sync_cost
from app.services.azure_inventory import get_or_create_cloud_account
from tests.fixtures.azure_cost import RESPONSE_MIXED, VM_RESOURCE_ID, make_response


def test_map_cost_response_resource_attributable_and_non_attributable():
    rows = map_cost_response(RESPONSE_MIXED)

    assert len(rows) == 3
    vm_row, marketplace_row, support_row = rows

    assert vm_row["date"] == date(2026, 9, 15)
    assert vm_row["external_resource_id"] is not None
    assert vm_row["charge_type"] == "Usage"
    assert vm_row["amortized_cost"] == 12.3456
    assert vm_row["currency"] == "USD"

    # Cost Management returns an empty string, not null, for non-attributable
    # charges - map_cost_response normalizes that to None.
    assert marketplace_row["external_resource_id"] is None
    assert marketplace_row["charge_type"] == "Usage"

    assert support_row["external_resource_id"] is None
    assert support_row["charge_type"] == "Purchase"


def _seed_vm_resource(db_session):
    # get_or_create_cloud_account keys off settings.azure_subscription_id, so this
    # reuses whatever cloud account already exists for it rather than creating a
    # second one.
    account = get_or_create_cloud_account(db_session, settings.azure_subscription_id)
    vm = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id=VM_RESOURCE_ID,
        resource_type="microsoft.compute/virtualmachines",
        tags={},
        raw_metadata={},
    )
    db_session.add(vm)
    db_session.commit()
    return account, vm


def test_sync_cost_creates_records(db_session):
    account, vm = _seed_vm_resource(db_session)

    def fake_fetch(subscription_id, lookback_days):
        return RESPONSE_MIXED

    summary = sync_cost(db_session, fetch=fake_fetch)

    assert summary.found == 3
    assert summary.created == 3
    assert summary.updated == 0

    records = (
        db_session.query(CostRecord).filter_by(cloud_account_id=account.id, date=date(2026, 9, 15)).all()
    )
    assert len(records) == 3

    # The fixture's resource ID differs in case from what's stored on the seeded
    # Resource - this confirms the case-insensitive match resolved it correctly.
    vm_record = next(r for r in records if r.resource_id == vm.id)
    assert float(vm_record.amortized_cost) == 12.3456
    assert vm_record.charge_type == "Usage"

    non_attributable = [r for r in records if r.resource_id is None]
    assert len(non_attributable) == 2
    # The two non-resource charges have different charge_type values, so they
    # don't collide under (cloud_account_id, resource_id=None, date) alone -
    # this is exactly the ambiguity the charge_type column resolves.
    assert {r.charge_type for r in non_attributable} == {"Usage", "Purchase"}


def test_sync_cost_upsert_does_not_duplicate_on_overlapping_window(db_session):
    account, vm = _seed_vm_resource(db_session)

    def fake_fetch(subscription_id, lookback_days):
        return RESPONSE_MIXED

    sync_cost(db_session, fetch=fake_fetch)

    def fake_fetch_overlapping(subscription_id, lookback_days):
        return make_response(
            [99.99, 20260915, VM_RESOURCE_ID, "Usage", "USD"],
            [5.00, 20260915, "", "Usage", "USD"],
            [50.00, 20260915, "", "Purchase", "USD"],
        )

    summary = sync_cost(db_session, fetch=fake_fetch_overlapping)

    assert summary.found == 3
    assert summary.created == 0
    assert summary.updated == 3

    records = (
        db_session.query(CostRecord).filter_by(cloud_account_id=account.id, date=date(2026, 9, 15)).all()
    )
    assert len(records) == 3  # still 3, not 6 - the overlapping run updated in place

    vm_record = next(r for r in records if r.resource_id == vm.id)
    assert float(vm_record.amortized_cost) == 99.99
