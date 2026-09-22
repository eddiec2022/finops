from datetime import date, datetime, timedelta, timezone

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.aws_rightsizing import build_aws_rightsizing_recommendations

LOOKBACK_DAYS = 14  # matches settings.idle_lookback_days default


def _seed_account(db_session, external_id: str) -> CloudAccount:
    return CloudAccount(provider=Provider.AWS, external_id=external_id, display_name="AWS Rightsizing Test Account")


def _add_instance(db_session, account, external_id, instance_type="m5.xlarge") -> Resource:
    instance = Resource(
        cloud_account_id=account.id,
        provider=Provider.AWS,
        external_resource_id=external_id,
        resource_type="aws::ec2::instance",
        resource_group="EC2 instance",
        region="us-east-1",
        tags={},
        sku=instance_type,
        raw_metadata={},
    )
    db_session.add(instance)
    db_session.flush()
    return instance


def _add_cpu_readings(db_session, resource, days, value, metric_name="CPUUtilization"):
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


def test_flags_idle_instance_with_suggested_type_and_estimated_savings(db_session):
    account = _seed_account(db_session, "test-account-rightsizing-idle")
    db_session.add(account)
    db_session.flush()
    instance = _add_instance(db_session, account, "i-idle", instance_type="m5.xlarge")
    _add_cpu_readings(db_session, instance, days=LOOKBACK_DAYS, value=2.0)
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, instance, date(2026, 9, 1) + timedelta(days=offset), 10.0)
    db_session.commit()

    result = build_aws_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["provider"] == "aws"
    assert rec["external_resource_id"] == "i-idle"
    assert rec["current_sku"] == "m5.xlarge"
    assert rec["suggested_sku"] == "m5.large"
    assert rec["avg_cpu_percent"] == 2.0
    assert rec["estimated_monthly_savings"] == 10.0 * 0.5 * 30


def test_does_not_flag_busy_instance(db_session):
    account = _seed_account(db_session, "test-account-rightsizing-busy")
    db_session.add(account)
    db_session.flush()
    instance = _add_instance(db_session, account, "i-busy")
    _add_cpu_readings(db_session, instance, days=LOOKBACK_DAYS, value=80.0)
    db_session.commit()

    result = build_aws_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_excludes_instance_with_insufficient_utilization_history(db_session):
    account = _seed_account(db_session, "test-account-rightsizing-insufficient")
    db_session.add(account)
    db_session.flush()
    instance = _add_instance(db_session, account, "i-new")
    _add_cpu_readings(db_session, instance, days=3, value=1.0)
    db_session.commit()

    result = build_aws_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flags_idle_smallest_instance_without_a_specific_suggested_type(db_session):
    account = _seed_account(db_session, "test-account-rightsizing-nano")
    db_session.add(account)
    db_session.flush()
    instance = _add_instance(db_session, account, "i-nano", instance_type="t3.nano")
    _add_cpu_readings(db_session, instance, days=LOOKBACK_DAYS, value=1.0)
    db_session.commit()

    result = build_aws_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["suggested_sku"] is None
    assert rec["estimated_monthly_savings"] is None


def test_response_includes_the_settings_used(db_session):
    account = _seed_account(db_session, "test-account-rightsizing-settings")
    db_session.add(account)
    db_session.flush()
    db_session.commit()

    result = build_aws_rightsizing_recommendations(db_session, cloud_account_id=account.id)

    assert result["idle_cpu_threshold_percent"] == settings.idle_cpu_threshold_percent
    assert result["idle_lookback_days"] == settings.idle_lookback_days


def test_endpoint_merges_aws_recommendations_when_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "999988887777")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")

    from app.services.aws_inventory import get_or_create_aws_cloud_account

    account = get_or_create_aws_cloud_account(db_session, settings.aws_account_id)
    instance = _add_instance(db_session, account, "i-endpoint-idle")
    _add_cpu_readings(db_session, instance, days=settings.idle_lookback_days, value=1.0)
    for offset in range(settings.idle_lookback_days):
        _add_cost(db_session, account, instance, date(2026, 9, 1) + timedelta(days=offset), 5.0)
    db_session.commit()

    response = client.get("/api/v1/recommendations/rightsizing")

    assert response.status_code == 200
    body = response.json()
    external_ids = {rec["external_resource_id"] for rec in body["recommendations"]}
    assert "i-endpoint-idle" in external_ids
