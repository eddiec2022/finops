from datetime import date, timedelta

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.azure_inventory import get_or_create_cloud_account
from app.services.idle_resources import build_idle_resource_recommendations

LOOKBACK_DAYS = 14  # matches settings.idle_lookback_days default


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AZURE, external_id=external_id, display_name="Idle Resources Test Sub")
    db_session.add(account)
    db_session.flush()
    return account


def _add_resource(db_session, account, resource_type, external_id, raw_metadata, resource_group="rg-a") -> Resource:
    resource = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id=external_id,
        resource_type=resource_type,
        resource_group=resource_group,
        region="eastus",
        tags={},
        raw_metadata=raw_metadata,
    )
    db_session.add(resource)
    db_session.flush()
    return resource


def _add_cost(db_session, account, resource, day, amount):
    db_session.add(
        CostRecord(
            cloud_account_id=account.id,
            resource_id=resource.id,
            date=day,
            amortized_cost=amount,
            currency="USD",
            granularity="Daily",
            charge_type="Usage",
        )
    )


def test_flags_unattached_disk_with_estimated_waste(db_session):
    account = _seed_account(db_session, "test-sub-idle-disk")
    disk = _add_resource(
        db_session,
        account,
        "microsoft.compute/disks",
        "disk-unattached",
        {"properties": {"diskState": "Unattached"}},
    )
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, disk, date(2026, 9, 1) + timedelta(days=offset), 2.0)
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["external_resource_id"] == "disk-unattached"
    assert rec["reason"] == "unattached_disk"
    assert rec["estimated_monthly_waste"] == 2.0 * 30


def test_does_not_flag_attached_disk(db_session):
    account = _seed_account(db_session, "test-sub-idle-disk-attached")
    _add_resource(
        db_session,
        account,
        "microsoft.compute/disks",
        "disk-attached",
        {"properties": {"diskState": "Attached"}},
    )
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flags_unused_public_ip(db_session):
    account = _seed_account(db_session, "test-sub-idle-ip")
    ip = _add_resource(
        db_session,
        account,
        "microsoft.network/publicipaddresses",
        "ip-unused",
        {"properties": {}},
    )
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, ip, date(2026, 9, 1) + timedelta(days=offset), 0.1)
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["reason"] == "unused_public_ip"
    assert rec["estimated_monthly_waste"] == round(0.1 * 30, 2)


def test_does_not_flag_associated_public_ip(db_session):
    account = _seed_account(db_session, "test-sub-idle-ip-associated")
    _add_resource(
        db_session,
        account,
        "microsoft.network/publicipaddresses",
        "ip-associated",
        {"properties": {"ipConfiguration": {"id": "/some/nic/ipconfig1"}}},
    )
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flags_stopped_not_deallocated_vm(db_session):
    account = _seed_account(db_session, "test-sub-idle-vm-stopped")
    vm = _add_resource(
        db_session,
        account,
        "microsoft.compute/virtualmachines",
        "vm-stopped",
        {"properties": {"extended": {"instanceView": {"powerState": {"code": "PowerState/stopped"}}}}},
    )
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, vm, date(2026, 9, 1) + timedelta(days=offset), 5.0)
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["reason"] == "stopped_not_deallocated_vm"
    assert rec["estimated_monthly_waste"] == 5.0 * 30


def test_does_not_flag_deallocated_vm(db_session):
    account = _seed_account(db_session, "test-sub-idle-vm-deallocated")
    _add_resource(
        db_session,
        account,
        "microsoft.compute/virtualmachines",
        "vm-deallocated",
        {"properties": {"extended": {"instanceView": {"powerState": {"code": "PowerState/deallocated"}}}}},
    )
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_does_not_flag_running_vm(db_session):
    account = _seed_account(db_session, "test-sub-idle-vm-running")
    _add_resource(
        db_session,
        account,
        "microsoft.compute/virtualmachines",
        "vm-running",
        {"properties": {"extended": {"instanceView": {"powerState": {"code": "PowerState/running"}}}}},
    )
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flagged_resource_with_no_cost_data_has_null_waste_estimate(db_session):
    account = _seed_account(db_session, "test-sub-idle-no-cost")
    _add_resource(
        db_session,
        account,
        "microsoft.compute/disks",
        "disk-no-cost-history",
        {"properties": {"diskState": "Unattached"}},
    )
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["estimated_monthly_waste"] is None
    assert "no cost data" in rec["waste_note"].lower()


def test_response_includes_lookback_days_setting(db_session):
    account = _seed_account(db_session, "test-sub-idle-settings")
    db_session.commit()

    result = build_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["idle_lookback_days"] == settings.idle_lookback_days


def test_endpoint_returns_200_against_seeded_data(client, db_session):
    account = get_or_create_cloud_account(db_session, settings.azure_subscription_id)
    _add_resource(
        db_session,
        account,
        "microsoft.compute/disks",
        "disk-endpoint-unattached",
        {"properties": {"diskState": "Unattached"}},
    )
    db_session.commit()

    response = client.get("/api/v1/recommendations/idle-resources")

    assert response.status_code == 200
    body = response.json()
    assert body["idle_lookback_days"] == settings.idle_lookback_days
    external_ids = {rec["external_resource_id"] for rec in body["recommendations"]}
    assert "disk-endpoint-unattached" in external_ids
