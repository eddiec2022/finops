from datetime import date, timedelta

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.aws_non_peak_scheduling import build_aws_non_peak_scheduling_recommendations


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AWS, external_id=external_id, display_name="AWS Non-Peak Test Account")
    db_session.add(account)
    db_session.flush()
    return account


def _add_instance(db_session, account, external_id, name=None, tags=None) -> Resource:
    instance = Resource(
        cloud_account_id=account.id,
        provider=Provider.AWS,
        external_resource_id=external_id,
        name=name,
        resource_type="aws::ec2::instance",
        resource_group="EC2 instance",
        region="us-east-1",
        tags=tags or {},
        raw_metadata={},
    )
    db_session.add(instance)
    db_session.flush()
    return instance


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


def test_flags_instance_by_naming_convention(db_session):
    account = _seed_account(db_session, "test-account-nonpeak-naming")
    instance = _add_instance(db_session, account, "i-dev", name="web-dev-01")
    for offset in range(14):
        _add_cost(db_session, account, instance, date(2026, 9, 1) + timedelta(days=offset), 2.0)
    db_session.commit()

    result = build_aws_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["provider"] == "aws"
    assert rec["signals"]["naming"]["matched"] is True
    assert rec["estimated_monthly_savings"] is not None


def test_flags_instance_by_env_tag(db_session):
    account = _seed_account(db_session, "test-account-nonpeak-tag")
    _add_instance(db_session, account, "i-staging", name="web-01", tags={"env": "staging"})
    db_session.commit()

    result = build_aws_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["signals"]["tag"]["matched"] is True


def test_does_not_flag_production_instance_with_no_signals(db_session):
    account = _seed_account(db_session, "test-account-nonpeak-prod")
    _add_instance(db_session, account, "i-prod", name="web-prod-01", tags={"env": "production"})
    db_session.commit()

    result = build_aws_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_response_includes_business_hours_and_settings(db_session):
    account = _seed_account(db_session, "test-account-nonpeak-settings")
    db_session.commit()

    result = build_aws_non_peak_scheduling_recommendations(db_session, cloud_account_id=account.id)

    assert result["idle_lookback_days"] == settings.idle_lookback_days
    assert result["off_peak_usage_ratio_threshold"] == settings.off_peak_usage_ratio_threshold
    assert "UTC" in result["business_hours_definition"]


def test_endpoint_merges_aws_recommendations_when_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "999988887777")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")

    from app.services.aws_inventory import get_or_create_aws_cloud_account

    account = get_or_create_aws_cloud_account(db_session, settings.aws_account_id)
    _add_instance(db_session, account, "i-endpoint-dev", name="web-dev-endpoint")
    db_session.commit()

    response = client.get("/api/v1/recommendations/non-peak-scheduling")

    assert response.status_code == 200
    body = response.json()
    external_ids = {rec["external_resource_id"] for rec in body["recommendations"]}
    assert "i-endpoint-dev" in external_ids
