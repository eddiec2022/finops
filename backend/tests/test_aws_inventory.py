from datetime import datetime, timezone

import boto3
from moto import mock_aws

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource
from app.services.aws_inventory import (
    _enrich_elastic_ips,
    fetch_resources,
    get_or_create_aws_cloud_account,
    map_resource,
    parse_arn,
    sync_aws_inventory,
    upsert_resources,
)
from tests.fixtures.aws_resources import EBS_VOLUME_ROW, EC2_INSTANCE_ROW, S3_BUCKET_ROW, UNLISTED_TYPE_ROW


def test_parse_arn_ec2_instance():
    parsed = parse_arn("arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0")

    assert parsed["service"] == "ec2"
    assert parsed["region"] == "us-east-1"
    assert parsed["account_id"] == "123456789012"
    assert parsed["resource_type"] == "instance"
    assert parsed["resource_id"] == "i-0123456789abcdef0"


def test_parse_arn_s3_bucket_has_no_region_or_account():
    # S3 ARNs omit the region and account-id segments entirely, and have no
    # "type/id" split - the whole resource segment is just the bucket name.
    parsed = parse_arn("arn:aws:s3:::my-finops-bucket")

    assert parsed["service"] == "s3"
    assert parsed["region"] is None
    assert parsed["account_id"] is None
    assert parsed["resource_type"] is None
    assert parsed["resource_id"] == "my-finops-bucket"


def test_parse_arn_colon_separated_resource():
    # Some services use "type:id" instead of "type/id" in the resource segment.
    parsed = parse_arn("arn:aws:sns:us-east-1:123456789012:topic:my-topic")

    assert parsed["resource_type"] == "topic"
    assert parsed["resource_id"] == "my-topic"


def test_map_resource_ec2_instance():
    mapped = map_resource(EC2_INSTANCE_ROW)

    assert mapped["provider"] == Provider.AWS
    assert mapped["external_resource_id"] == EC2_INSTANCE_ROW["arn"].lower()
    assert mapped["name"] == "web-01"
    assert mapped["resource_type"] == "aws::ec2::instance"
    assert mapped["region"] == "us-east-1"
    assert mapped["resource_group"] == "EC2 instance"
    assert mapped["tags"] == {"Name": "web-01", "env": "prod"}
    assert mapped["sku"] == "t3.micro"
    assert mapped["created_at"] == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert mapped["raw_metadata"] == EC2_INSTANCE_ROW


def test_map_resource_ebs_volume():
    mapped = map_resource(EBS_VOLUME_ROW)

    assert mapped["resource_type"] == "aws::ec2::volume"
    assert mapped["resource_group"] == "EBS volume"
    assert mapped["sku"] == "gp3"
    assert mapped["name"] is None  # no Name tag on this fixture


def test_map_resource_s3_bucket_no_region_no_sku():
    mapped = map_resource(S3_BUCKET_ROW)

    assert mapped["resource_type"] == "aws::s3::resource"
    assert mapped["resource_group"] == "S3 bucket"
    assert mapped["region"] is None
    assert mapped["sku"] is None
    assert "created_at" not in mapped  # no enrichment call for S3 in v1


def test_map_resource_unlisted_type_falls_back_to_humanized_label():
    mapped = map_resource(UNLISTED_TYPE_ROW)

    assert mapped["resource_type"] == "aws::rds::db"
    # Not in _RESOURCE_TYPE_LABELS - falls back to a generic humanized label
    # rather than a raw/unreadable string.
    assert mapped["resource_group"] == "RDS db"


def _seed_aws_account(db_session) -> CloudAccount:
    return get_or_create_aws_cloud_account(db_session, "123456789012")


def test_upsert_resources_creates_and_updates(db_session):
    account = _seed_aws_account(db_session)
    before = db_session.query(Resource).count()

    mapped = [map_resource(EC2_INSTANCE_ROW), map_resource(EBS_VOLUME_ROW)]
    created, updated = upsert_resources(db_session, account, mapped)

    assert created == 2
    assert updated == 0
    assert db_session.query(Resource).count() == before + 2

    updated_row = {**EC2_INSTANCE_ROW, "tags": {"Name": "web-01", "env": "staging"}}
    created2, updated2 = upsert_resources(db_session, account, [map_resource(updated_row)])

    assert created2 == 0
    assert updated2 == 1
    assert db_session.query(Resource).count() == before + 2  # still 2, not 3

    resource = db_session.query(Resource).filter_by(external_resource_id=EC2_INSTANCE_ROW["arn"].lower()).one()
    assert resource.tags == {"Name": "web-01", "env": "staging"}
    assert resource.provider == Provider.AWS


def test_upsert_resources_case_drift_updates_existing_row_not_duplicate(db_session):
    """Regression test mirroring Task 18's Azure fix - reuses the same
    lowercase-at-write-time normalization, so an ARN returned in different casing
    on a later sync must update the existing row, not create a second one."""
    account = _seed_aws_account(db_session)
    before = db_session.query(Resource).count()

    upsert_resources(db_session, account, [map_resource(EC2_INSTANCE_ROW)])
    assert db_session.query(Resource).count() == before + 1

    recased_row = {**EC2_INSTANCE_ROW, "arn": EC2_INSTANCE_ROW["arn"].upper()}
    created, updated = upsert_resources(db_session, account, [map_resource(recased_row)])

    assert created == 0
    assert updated == 1
    assert db_session.query(Resource).count() == before + 1


def _fake_fetch(rows):
    def fetch(region: str):
        return rows

    return fetch


def test_sync_aws_inventory_creates_resources(db_session):
    before = db_session.query(Resource).count()

    summary = sync_aws_inventory(db_session, fetch=_fake_fetch([EC2_INSTANCE_ROW, EBS_VOLUME_ROW]))

    assert summary.found == 2
    assert summary.created == 2
    assert summary.updated == 0
    assert db_session.query(Resource).count() == before + 2
    assert db_session.query(CloudAccount).filter_by(provider=Provider.AWS, external_id=settings.aws_account_id).count() == 1


@mock_aws
def test_fetch_resources_moto_ec2_instance_discovered_and_enriched(monkeypatch):
    """End-to-end against moto's simulated AWS backend (not a hand-built fixture)
    - creates a real EC2 instance and volume, tags them, and confirms
    fetch_resources() discovers + enriches them via the real Tagging API and
    describe_* calls, not injected fake data."""
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")

    region = "us-east-1"
    ec2 = boto3.client("ec2", region_name=region, aws_access_key_id="testing", aws_secret_access_key="testing")

    reservation = ec2.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "moto-web-01"}, {"Key": "env", "Value": "test"}]}
        ],
    )
    instance_id = reservation["Instances"][0]["InstanceId"]

    volume = ec2.create_volume(AvailabilityZone=f"{region}a", Size=8, VolumeType="gp3")
    ec2.create_tags(Resources=[volume["VolumeId"]], Tags=[{"Key": "env", "Value": "test"}])

    rows = fetch_resources(region)

    instance_rows = [r for r in rows if r["resource_id"] == instance_id]
    assert len(instance_rows) == 1
    assert instance_rows[0]["service"] == "ec2"
    assert instance_rows[0]["resource_type"] == "instance"
    assert instance_rows[0]["tags"]["Name"] == "moto-web-01"
    assert instance_rows[0]["instance_type"] == "t3.micro"
    assert instance_rows[0]["state"] == "running"
    assert "created_at" in instance_rows[0]

    volume_rows = [r for r in rows if r["resource_id"] == volume["VolumeId"]]
    assert len(volume_rows) == 1
    assert volume_rows[0]["volume_type"] == "gp3"
    assert volume_rows[0]["state"] == "available"
    assert volume_rows[0]["tags"] == {"env": "test"}


@mock_aws
def test_enrich_elastic_ips_against_real_describe_addresses(monkeypatch):
    """Real API-shape finding: moto's Tagging API (get_resources) does not
    discover Elastic IPs at all, even tagged ones (confirmed: get_resources()
    returns an empty list for an allocated+tagged EIP, while describe_addresses
    correctly shows the tag) - a moto-specific gap, not real AWS behavior (AWS's
    real Tagging API does return Elastic IPs). So the full
    fetch_resources()-discovers-an-EIP-via-tagging path can't be exercised
    end-to-end against moto - this test instead calls _enrich_elastic_ips
    directly against a real describe_addresses call, which IS moto-supported,
    to at least confirm that half of the pipeline. Flagged for Task 21's live
    pass to specifically verify EIP discovery via the Tagging API works against
    the real account."""
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")

    ec2 = boto3.client("ec2", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
    unassociated = ec2.allocate_address(Domain="vpc")
    associated_alloc = ec2.allocate_address(Domain="vpc")
    reservation = ec2.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
    instance_id = reservation["Instances"][0]["InstanceId"]
    ec2.associate_address(AllocationId=associated_alloc["AllocationId"], InstanceId=instance_id)

    rows = [
        {"service": "ec2", "resource_type": "elastic-ip", "resource_id": unassociated["AllocationId"], "tags": {}},
        {"service": "ec2", "resource_type": "elastic-ip", "resource_id": associated_alloc["AllocationId"], "tags": {}},
    ]
    _enrich_elastic_ips(ec2, rows)

    by_id = {row["resource_id"]: row for row in rows}
    assert by_id[unassociated["AllocationId"]]["associated"] is False
    assert by_id[associated_alloc["AllocationId"]]["associated"] is True


@mock_aws
def test_sync_aws_inventory_end_to_end_against_moto(db_session, monkeypatch):
    """Full sync_aws_inventory() run against moto - real discovery, real
    enrichment, real map_resource, real DB upsert, no injected fake fetch."""
    monkeypatch.setattr(settings, "aws_access_key_id", "testing")
    monkeypatch.setattr(settings, "aws_secret_access_key", "testing")
    monkeypatch.setattr(settings, "aws_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_account_id", "999988887777")

    ec2 = boto3.client("ec2", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
    ec2.run_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "moto-web-02"}]}],
    )

    before = db_session.query(Resource).count()
    summary = sync_aws_inventory(db_session)

    assert summary.found == 1
    assert summary.created == 1
    assert db_session.query(Resource).count() == before + 1

    resource = db_session.query(Resource).filter_by(name="moto-web-02").one()
    assert resource.provider == Provider.AWS
    assert resource.resource_group == "EC2 instance"
