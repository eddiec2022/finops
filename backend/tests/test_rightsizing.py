from datetime import date, datetime, timedelta, timezone

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.azure_inventory import get_or_create_cloud_account
from app.services.rightsizing import build_rightsizing_recommendations

LOOKBACK_DAYS = 14  # matches settings.idle_lookback_days default


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AZURE, external_id=external_id, display_name="Rightsizing Test Sub")
    db_session.add(account)
    db_session.flush()
    return account


def _add_vm(db_session, account, external_id, sku="Standard_D4s_v3", resource_group="rg-a") -> Resource:
    vm = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id=external_id,
        resource_type="microsoft.compute/virtualmachines",
        resource_group=resource_group,
        region="eastus",
        tags={},
        sku=sku,
        raw_metadata={},
    )
    db_session.add(vm)
    db_session.flush()
    return vm


def _add_cpu_readings(db_session, resource, days, value, metric_name="Percentage CPU"):
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    for day in range(days):
        db_session.add(
            UtilizationMetric(
                resource_id=resource.id,
                metric_name=metric_name,
                timestamp=start + timedelta(days=day),
                value=value,
                unit="Percent",
            )
        )


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


def test_flags_idle_vm_with_suggested_sku_and_estimated_savings(db_session):
    account = _seed_account(db_session, "test-sub-rightsizing-idle")
    vm = _add_vm(db_session, account, "vm-idle", sku="Standard_D4s_v3")
    _add_cpu_readings(db_session, vm, days=LOOKBACK_DAYS, value=2.0)
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, vm, date(2026, 9, 1) + timedelta(days=offset), 10.0)
    db_session.commit()

    result = build_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["external_resource_id"] == "vm-idle"
    assert rec["current_sku"] == "Standard_D4s_v3"
    assert rec["suggested_sku"] == "Standard_D2s_v3"
    assert rec["avg_cpu_percent"] == 2.0
    assert rec["estimated_monthly_savings"] == 10.0 * 0.5 * 30


def test_does_not_flag_busy_vm(db_session):
    account = _seed_account(db_session, "test-sub-rightsizing-busy")
    vm = _add_vm(db_session, account, "vm-busy")
    _add_cpu_readings(db_session, vm, days=LOOKBACK_DAYS, value=80.0)
    db_session.commit()

    result = build_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_excludes_vm_with_insufficient_utilization_history(db_session):
    account = _seed_account(db_session, "test-sub-rightsizing-insufficient")
    vm = _add_vm(db_session, account, "vm-new")
    # Only 3 days of history against a 14-day lookback window, even though
    # clearly idle - must be excluded, not flagged on partial data.
    _add_cpu_readings(db_session, vm, days=3, value=1.0)
    db_session.commit()

    result = build_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flags_idle_app_service_without_a_specific_suggested_tier(db_session):
    account = _seed_account(db_session, "test-sub-rightsizing-appservice")
    app_service = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="app-idle",
        resource_type="microsoft.web/sites",
        resource_group="rg-a",
        region="eastus",
        tags={},
        sku="S2",
        raw_metadata={},
    )
    db_session.add(app_service)
    db_session.flush()
    _add_cpu_readings(db_session, app_service, days=LOOKBACK_DAYS, value=1.5, metric_name="CpuPercentage")
    db_session.commit()

    result = build_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["current_sku"] == "S2"
    assert rec["suggested_sku"] is None
    assert "tier" in rec["suggestion_note"].lower()
    assert rec["estimated_monthly_savings"] is None


def test_response_includes_the_settings_used(db_session):
    account = _seed_account(db_session, "test-sub-rightsizing-settings")
    db_session.commit()

    result = build_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert result["idle_cpu_threshold_percent"] == settings.idle_cpu_threshold_percent
    assert result["idle_lookback_days"] == settings.idle_lookback_days


def test_endpoint_returns_200_against_seeded_data(client, db_session):
    account = get_or_create_cloud_account(db_session, settings.azure_subscription_id)
    vm = _add_vm(db_session, account, "vm-endpoint-idle")
    _add_cpu_readings(db_session, vm, days=settings.idle_lookback_days, value=1.0)
    for offset in range(settings.idle_lookback_days):
        _add_cost(db_session, account, vm, date(2026, 9, 1) + timedelta(days=offset), 5.0)
    db_session.commit()

    response = client.get("/api/v1/recommendations/rightsizing")

    assert response.status_code == 200
    body = response.json()
    assert body["idle_lookback_days"] == settings.idle_lookback_days
    external_ids = {rec["external_resource_id"] for rec in body["recommendations"]}
    assert "vm-endpoint-idle" in external_ids
