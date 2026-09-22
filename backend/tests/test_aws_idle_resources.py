from datetime import date, timedelta

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.cost_record import CostRecord
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.aws_idle_resources import build_aws_idle_resource_recommendations
from app.services.aws_inventory import get_or_create_aws_cloud_account

LOOKBACK_DAYS = 14  # matches settings.idle_lookback_days default


def _seed_account(db_session, external_id: str) -> CloudAccount:
    account = CloudAccount(provider=Provider.AWS, external_id=external_id, display_name="AWS Idle Resources Test Account")
    db_session.add(account)
    db_session.flush()
    return account


def _add_resource(db_session, account, resource_type, external_id, raw_metadata, resource_group="EC2 instance") -> Resource:
    resource = Resource(
        cloud_account_id=account.id,
        provider=Provider.AWS,
        external_resource_id=external_id,
        resource_type=resource_type,
        resource_group=resource_group,
        region="us-east-1",
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


def test_flags_unattached_ebs_volume_with_estimated_waste(db_session):
    account = _seed_account(db_session, "test-account-idle-volume")
    volume = _add_resource(db_session, account, "aws::ec2::volume", "vol-unattached", {"state": "available"}, "EBS volume")
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, volume, date(2026, 9, 1) + timedelta(days=offset), 1.5)
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["provider"] == "aws"
    assert rec["external_resource_id"] == "vol-unattached"
    assert rec["reason"] == "unattached_ebs_volume"
    assert rec["estimated_monthly_waste"] == 1.5 * 30


def test_does_not_flag_in_use_volume(db_session):
    account = _seed_account(db_session, "test-account-idle-volume-attached")
    _add_resource(db_session, account, "aws::ec2::volume", "vol-in-use", {"state": "in-use"}, "EBS volume")
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flags_unassociated_elastic_ip(db_session):
    account = _seed_account(db_session, "test-account-idle-eip")
    eip = _add_resource(db_session, account, "aws::ec2::elastic-ip", "eip-unassociated", {"associated": False}, "Elastic IP")
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, eip, date(2026, 9, 1) + timedelta(days=offset), 0.1)
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["reason"] == "unassociated_elastic_ip"
    assert rec["estimated_monthly_waste"] == round(0.1 * 30, 2)


def test_does_not_flag_associated_elastic_ip(db_session):
    account = _seed_account(db_session, "test-account-idle-eip-associated")
    _add_resource(db_session, account, "aws::ec2::elastic-ip", "eip-associated", {"associated": True}, "Elastic IP")
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flags_stopped_ec2_instance(db_session):
    account = _seed_account(db_session, "test-account-idle-instance-stopped")
    instance = _add_resource(db_session, account, "aws::ec2::instance", "i-stopped", {"state": "stopped"})
    for offset in range(LOOKBACK_DAYS):
        _add_cost(db_session, account, instance, date(2026, 9, 1) + timedelta(days=offset), 0.5)
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["reason"] == "stopped_ec2_instance"
    assert rec["estimated_monthly_waste"] == 0.5 * 30


def test_does_not_flag_running_instance(db_session):
    account = _seed_account(db_session, "test-account-idle-instance-running")
    _add_resource(db_session, account, "aws::ec2::instance", "i-running", {"state": "running"})
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["recommendations"] == []


def test_flagged_resource_with_no_cost_data_has_null_waste_estimate(db_session):
    account = _seed_account(db_session, "test-account-idle-no-cost")
    _add_resource(db_session, account, "aws::ec2::volume", "vol-no-cost-history", {"state": "available"}, "EBS volume")
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert len(result["recommendations"]) == 1
    rec = result["recommendations"][0]
    assert rec["estimated_monthly_waste"] is None
    assert "no cost data" in rec["waste_note"].lower()


def test_response_includes_lookback_days_setting(db_session):
    account = _seed_account(db_session, "test-account-idle-settings")
    db_session.commit()

    result = build_aws_idle_resource_recommendations(db_session, cloud_account_id=account.id)

    assert result["idle_lookback_days"] == settings.idle_lookback_days


def test_endpoint_merges_aws_recommendations_when_configured(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "aws_account_id", "999988887777")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")

    account = get_or_create_aws_cloud_account(db_session, settings.aws_account_id)
    _add_resource(db_session, account, "aws::ec2::volume", "vol-endpoint-unattached", {"state": "available"}, "EBS volume")
    db_session.commit()

    response = client.get("/api/v1/recommendations/idle-resources")

    assert response.status_code == 200
    body = response.json()
    external_ids = {rec["external_resource_id"] for rec in body["recommendations"]}
    assert "vol-endpoint-unattached" in external_ids
    providers = {rec["provider"] for rec in body["recommendations"] if "vol-endpoint-unattached" == rec["external_resource_id"]}
    assert providers == {"aws"}


def test_endpoint_does_not_call_aws_when_unconfigured(client, db_session, monkeypatch):
    # AWS settings unset (default) - the endpoint must not attempt any AWS
    # call at all, same "Azure's code path stays identical" guarantee Task 19
    # established for the sync endpoints.
    monkeypatch.setattr(settings, "aws_account_id", "")
    monkeypatch.setattr(settings, "aws_region", "")
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")

    response = client.get("/api/v1/recommendations/idle-resources")

    assert response.status_code == 200
