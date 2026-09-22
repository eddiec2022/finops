from datetime import datetime, timedelta, timezone

import boto3
from moto import mock_aws

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.aws_cpu_metrics import AWS_CPU_METRIC_BY_RESOURCE_TYPE
from app.services.aws_utilization import fetch_metrics, map_metric_response, sync_aws_utilization
from tests.fixtures.aws_cloudwatch import CPU_RESPONSE, EMPTY_RESPONSE, T0, T1


def test_map_metric_response_flattens_datapoints():
    rows = map_metric_response(CPU_RESPONSE, "CPUUtilization")

    assert rows == [
        {"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T0, "value": 12.5},
        {"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T1, "value": 8.3},
    ]


def test_map_metric_response_empty_datapoints():
    rows = map_metric_response(EMPTY_RESPONSE, "CPUUtilization")

    assert rows == []


def test_fetch_metrics_ec2_instance():
    def fake_query_metric(namespace, dimension_name, resource_id, metric_name, lookback_days):
        assert namespace == "AWS/EC2"
        assert dimension_name == "InstanceId"
        return CPU_RESPONSE

    rows = fetch_metrics("aws::ec2::instance", "i-1", ["CPUUtilization"], 14, query_metric=fake_query_metric)

    assert len(rows) == 2
    assert {row["metric_name"] for row in rows} == {"CPUUtilization"}


def test_fetch_metrics_no_data_returns_empty_not_an_error():
    def fake_query_metric(namespace, dimension_name, resource_id, metric_name, lookback_days):
        return EMPTY_RESPONSE

    rows = fetch_metrics("aws::ec2::instance", "i-1", ["CPUUtilization"], 14, query_metric=fake_query_metric)

    assert rows == []


def _seed_instance(db_session, instance_id="i-1") -> Resource:
    account = CloudAccount(provider=Provider.AWS, external_id="999988887777", display_name="Test Account")
    db_session.add(account)
    db_session.flush()
    instance = Resource(
        cloud_account_id=account.id,
        provider=Provider.AWS,
        external_resource_id=f"arn:aws:ec2:us-east-1:999988887777:instance/{instance_id}",
        resource_type="aws::ec2::instance",
        tags={},
        raw_metadata={"resource_id": instance_id},
    )
    db_session.add(instance)
    db_session.commit()
    return instance


def test_sync_aws_utilization_creates_metrics(db_session):
    before_processed = (
        db_session.query(Resource).filter(Resource.resource_type.in_(AWS_CPU_METRIC_BY_RESOURCE_TYPE.keys())).count()
    )
    instance = _seed_instance(db_session)

    def fake_fetch(resource_type, resource_id, metric_names, lookback_days):
        if resource_id != "i-1":
            return []
        return [{"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T0, "value": 12.5}]

    summary = sync_aws_utilization(db_session, fetch=fake_fetch)

    assert summary.resources_processed == before_processed + 1
    assert summary.metrics_found == 1
    assert summary.created == 1
    assert summary.updated == 0
    assert db_session.query(UtilizationMetric).filter_by(resource_id=instance.id).count() == 1


def test_sync_aws_utilization_upsert_does_not_duplicate_on_overlapping_window(db_session):
    instance = _seed_instance(db_session)

    def fake_fetch(resource_type, resource_id, metric_names, lookback_days):
        return [
            {"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T0, "value": 12.5},
            {"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T1, "value": 8.3},
        ]

    sync_aws_utilization(db_session, fetch=fake_fetch)

    def fake_fetch_overlapping(resource_type, resource_id, metric_names, lookback_days):
        return [
            {"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T0, "value": 99.0},
            {"metric_name": "CPUUtilization", "unit": "Percent", "timestamp": T1, "value": 8.3},
        ]

    summary = sync_aws_utilization(db_session, fetch=fake_fetch_overlapping)

    assert summary.created == 0
    assert summary.updated == 2
    updated_point = (
        db_session.query(UtilizationMetric).filter_by(resource_id=instance.id, metric_name="CPUUtilization", timestamp=T0).one()
    )
    assert updated_point.value == 99.0


def test_sync_aws_utilization_skips_resource_with_no_raw_resource_id(db_session):
    account = CloudAccount(provider=Provider.AWS, external_id="999988887777", display_name="Test Account")
    db_session.add(account)
    db_session.flush()
    # No "resource_id" key in raw_metadata - shouldn't happen for a real synced
    # resource, but must not crash if it does.
    db_session.add(
        Resource(
            cloud_account_id=account.id,
            provider=Provider.AWS,
            external_resource_id="arn:aws:ec2:us-east-1:999988887777:instance/i-broken",
            resource_type="aws::ec2::instance",
            tags={},
            raw_metadata={},
        )
    )
    db_session.commit()

    def fake_fetch(resource_type, resource_id, metric_names, lookback_days):
        raise AssertionError("fetch should not be called for a resource with no raw resource_id")

    summary = sync_aws_utilization(db_session, fetch=fake_fetch)

    assert summary.metrics_found == 0


@mock_aws
def test_fetch_metrics_moto_real_cloudwatch_call(monkeypatch):
    """End-to-end against moto's simulated CloudWatch - confirms
    get_metric_statistics is actually callable and shaped as expected, not
    just that the injected-fixture unit tests above pass."""
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")

    cloudwatch = boto3.client(
        "cloudwatch", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing"
    )
    now = datetime.now(timezone.utc)
    cloudwatch.put_metric_data(
        Namespace="AWS/EC2",
        MetricData=[
            {
                "MetricName": "CPUUtilization",
                "Dimensions": [{"Name": "InstanceId", "Value": "i-moto1"}],
                "Timestamp": now - timedelta(minutes=5),
                "Value": 42.0,
                "Unit": "Percent",
            }
        ],
    )

    rows = fetch_metrics("aws::ec2::instance", "i-moto1", ["CPUUtilization"], 1)

    assert len(rows) >= 1
    assert rows[0]["metric_name"] == "CPUUtilization"
    assert rows[0]["value"] == 42.0
