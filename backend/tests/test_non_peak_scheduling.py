from datetime import date, datetime, timedelta, timezone

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.azure_inventory import get_or_create_cloud_account
from app.services.non_peak_scheduling import build_non_peak_scheduling_recommendations

LOOKBACK_DAYS = 14  # matches settings.idle_lookback_days default
# 2026-09-14 is a Monday - starting here gives a clean 2-full-week window.
MONDAY = datetime(2026, 9, 14, tzinfo=timezone.utc)


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AZURE, external_id=external_id, display_name="Non-Peak Test Sub")
    db_session.add(account)
    db_session.flush()
    return account


def _add_vm(db_session, account, external_id, name, tags=None, resource_group="rg-a") -> Resource:
    vm = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id=external_id,
        resource_type="microsoft.compute/virtualmachines",
        resource_group=resource_group,
        region="eastus",
        tags=tags or {},
        raw_metadata={"name": name},
    )
    db_session.add(vm)
    db_session.flush()
    return vm


def _add_readings(db_session, resource, entries, metric_name="Percentage CPU"):
    for ts, value in entries:
        db_session.add(
            UtilizationMetric(resource_id=resource.id, metric_name=metric_name, timestamp=ts, value=value, unit="Percent")
        )


def _weekday_readings(start, days, hour, value):
    return [
        (start.replace(hour=hour) + timedelta(days=d), value)
        for d in range(days)
        if (start + timedelta(days=d)).weekday() < 5
    ]


def _daily_readings(start, days, hour, value):
    return [(start.replace(hour=hour) + timedelta(days=d), value) for d in range(days)]


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


def test_flags_resource_by_tag_alone(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-tag")
    vm = _add_vm(db_session, account, "vm-tag-dev", "app-prod-lookalike-01", tags={"environment": "dev"})
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, vm, date(2026, 9, 1) + timedelta(days=offset), 4.0)
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["external_resource_id"] == "vm-tag-dev"
    assert rec["signals"]["tag"]["matched"] is True
    assert rec["signals"]["naming"]["matched"] is False
    assert rec["estimated_monthly_savings"] is not None


def test_flags_resource_by_name_alone(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-name")
    _add_vm(db_session, account, "vm-name-test", "app-test-01", tags={"environment": "production"})
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["signals"]["tag"]["matched"] is False
    assert rec["signals"]["naming"]["matched"] is True


def test_flags_production_tagged_resource_on_usage_pattern_alone(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-usage")
    vm = _add_vm(db_session, account, "vm-prod-but-dips", "app-prod-01", tags={"environment": "production"})
    peak = _weekday_readings(MONDAY, LOOKBACK_DAYS, hour=13, value=80.0)
    off_peak = _daily_readings(MONDAY, LOOKBACK_DAYS, hour=2, value=5.0)
    _add_readings(db_session, vm, peak + off_peak)
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["signals"]["tag"]["matched"] is False
    assert rec["signals"]["naming"]["matched"] is False
    assert rec["signals"]["usage_pattern"]["matched"] is True
    assert rec["signals"]["usage_pattern"]["peak_avg_cpu_percent"] == 80.0
    assert rec["signals"]["usage_pattern"]["off_peak_avg_cpu_percent"] == 5.0


def test_does_not_flag_always_busy_production_resource(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-busy")
    vm = _add_vm(db_session, account, "vm-prod-busy", "app-prod-02", tags={"environment": "production"})
    peak = _weekday_readings(MONDAY, LOOKBACK_DAYS, hour=13, value=75.0)
    off_peak = _daily_readings(MONDAY, LOOKBACK_DAYS, hour=2, value=70.0)
    _add_readings(db_session, vm, peak + off_peak)
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_savings_estimate_uses_off_peak_fraction_of_week(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-savings")
    vm = _add_vm(db_session, account, "vm-savings-check", "app-test-savings", tags={})
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, vm, date(2026, 9, 1) + timedelta(days=offset), 10.0)
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    rec = result["recommendations"][0]
    # 10.0/day * 30 * (118/168 off-hours fraction of the week)
    expected = round(10.0 * 30 * (118 / 168), 2)
    assert rec["estimated_monthly_savings"] == expected


def test_flagged_resource_with_no_cost_data_has_null_savings(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-no-cost")
    _add_vm(db_session, account, "vm-no-cost-history", "app-dev-nocosthist", tags={})
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    rec = result["recommendations"][0]
    assert rec["estimated_monthly_savings"] is None
    assert "no cost data" in rec["savings_note"].lower()


def test_response_includes_settings_and_business_hours_definition(db_session):
    account = _seed_account(db_session, "test-sub-nonpeak-settings")
    db_session.commit()

    result = build_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert result["idle_lookback_days"] == settings.idle_lookback_days
    assert result["off_peak_usage_ratio_threshold"] == settings.off_peak_usage_ratio_threshold
    assert "UTC" in result["business_hours_definition"]


def test_endpoint_returns_200_against_seeded_data(client, db_session):
    account = get_or_create_cloud_account(db_session, settings.azure_subscription_id)
    _add_vm(db_session, account, "vm-endpoint-dev", "app-dev-endpoint", tags={"environment": "dev"})
    db_session.commit()

    response = client.get("/api/v1/recommendations/non-peak-scheduling")

    assert response.status_code == 200
    body = response.json()
    external_ids = {rec["external_resource_id"] for rec in body["recommendations"]}
    assert "vm-endpoint-dev" in external_ids
