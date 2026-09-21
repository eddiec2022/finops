from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import boto3
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource

# GOV-002 2.2 (adopted option 1): the Tagging API for discovery (ARNs + tags
# across most services in one call, no account setup like Config/Resource
# Explorer would need), layered with targeted describe_* calls per resource type
# for the fields Phase 1's schema needs (mirrors azure_inventory's Resource Graph
# `project` + azure_utilization's per-metric describe pattern). Only EC2
# instances and EBS volumes get describe_* enrichment for v1 (GOV-002 2.2) -
# every other tagged resource type still gets discovered and stored, just
# without SKU/creation-date.
_EC2_INSTANCE = ("ec2", "instance")
_EC2_VOLUME = ("ec2", "volume")

# GOV-002 Section 3's resolved "human-readable resource type" convention for
# resource_group - not exhaustive (deliberately, per the task's "don't try to
# cover every AWS service" instruction). Anything not listed here falls back to
# a generically humanized label in _resource_type_label rather than a raw ARN
# fragment, so the drill-down UI never shows something unreadable.
_RESOURCE_TYPE_LABELS: dict[tuple[str, str | None], str] = {
    ("ec2", "instance"): "EC2 instance",
    ("ec2", "volume"): "EBS volume",
    ("ec2", "network-interface"): "Network interface",
    ("ec2", "security-group"): "Security group",
    ("ec2", "vpc"): "VPC",
    ("ec2", "subnet"): "Subnet",
    ("ec2", "elastic-ip"): "Elastic IP",
    ("s3", None): "S3 bucket",
}


@dataclass
class SyncSummary:
    found: int
    created: int
    updated: int


def parse_arn(arn: str) -> dict[str, str | None]:
    """Split an ARN into its named parts.

    Format: arn:partition:service:region:account-id:resource - where `resource`
    is itself either `type/id`, `type:id`, or (S3's case) just a bare name with
    no type segment at all. Real API-shape gotcha found writing this: S3 bucket
    ARNs (`arn:aws:s3:::my-bucket`) omit both region and account-id entirely -
    there's no way to recover a bucket's region from its ARN alone; a real
    `get_bucket_location` call would be needed, which v1 doesn't make (S3 isn't
    one of the two describe_*-enriched types), so S3 resources land with
    region=None. Flagged for Task 20's live pass.
    """
    parts = arn.split(":", 5)
    service = parts[2] if len(parts) > 2 else ""
    region = parts[3] if len(parts) > 3 else None
    account_id = parts[4] if len(parts) > 4 else None
    resource_part = parts[5] if len(parts) > 5 else ""

    # Defensive: moto's simulated Tagging API returns EC2 resource ARNs with the
    # service name repeated as a prefix on the resource segment itself (observed
    # writing this: "ec2:instance/i-..." instead of real AWS's "instance/i-...")
    # - a no-op for genuine AWS ARNs, which never do this, but avoids parsing
    # "ec2" as a bogus resource type against moto's test double.
    prefix = f"{service}:"
    if resource_part.startswith(prefix):
        resource_part = resource_part[len(prefix) :]

    if "/" in resource_part:
        resource_type, resource_id = resource_part.split("/", 1)
    elif ":" in resource_part:
        resource_type, resource_id = resource_part.split(":", 1)
    else:
        resource_type, resource_id = None, resource_part

    return {
        "service": service,
        "region": region or None,
        "account_id": account_id or None,
        "resource_type": resource_type,
        "resource_id": resource_id,
    }


def _resource_type_label(service: str, resource_type: str | None) -> str:
    label = _RESOURCE_TYPE_LABELS.get((service, resource_type))
    if label:
        return label
    if resource_type:
        return f"{service.upper()} {resource_type.replace('-', ' ')}"
    return service.upper()


def _enrich_ec2_instances(ec2_client: Any, rows: list[dict[str, Any]]) -> None:
    targets = {row["resource_id"]: row for row in rows if (row["service"], row["resource_type"]) == _EC2_INSTANCE}
    if not targets:
        return
    # An empty InstanceIds list means "describe every instance in the account",
    # not "describe none" - the `if targets` guard above is load-bearing, not
    # just an optimization.
    response = ec2_client.describe_instances(InstanceIds=list(targets.keys()))
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            row = targets.get(instance["InstanceId"])
            if row is None:
                continue
            row["instance_type"] = instance.get("InstanceType")
            if instance.get("LaunchTime"):
                # ISO string, not the raw datetime boto3 returns - raw_metadata
                # stores this whole row as-is into a JSONB column, and a bare
                # datetime object isn't JSON-serializable (unlike Azure Resource
                # Graph, which only ever returns JSON-safe strings to begin
                # with). map_resource parses this back into a real datetime.
                row["created_at"] = instance["LaunchTime"].isoformat()


def _enrich_ebs_volumes(ec2_client: Any, rows: list[dict[str, Any]]) -> None:
    targets = {row["resource_id"]: row for row in rows if (row["service"], row["resource_type"]) == _EC2_VOLUME}
    if not targets:
        return
    response = ec2_client.describe_volumes(VolumeIds=list(targets.keys()))
    for volume in response.get("Volumes", []):
        row = targets.get(volume["VolumeId"])
        if row is None:
            continue
        row["volume_type"] = volume.get("VolumeType")
        if volume.get("CreateTime"):
            row["created_at"] = volume["CreateTime"].isoformat()


def fetch_resources(region: str) -> list[dict[str, Any]]:
    """Discover every tagged resource in the account/region via the Tagging API,
    then enrich EC2 instances and EBS volumes with a targeted describe_* call
    each. Untagged resources are invisible to the Tagging API - a real, inherent
    limitation of this discovery method (not a bug), worth knowing before
    reading inventory counts against what the AWS Console shows."""
    session = boto3.Session(
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=region,
    )
    tagging_client = session.client("resourcegroupstaggingapi")
    ec2_client = session.client("ec2")

    rows: list[dict[str, Any]] = []
    paginator = tagging_client.get_paginator("get_resources")
    for page in paginator.paginate():
        for item in page.get("ResourceTagMappingList", []):
            arn = item["ResourceARN"]
            parsed = parse_arn(arn)
            tags = {tag["Key"]: tag["Value"] for tag in item.get("Tags", [])}
            rows.append({"arn": arn, "tags": tags, **parsed})

    _enrich_ec2_instances(ec2_client, rows)
    _enrich_ebs_volumes(ec2_client, rows)

    return rows


def map_resource(row: dict[str, Any]) -> dict[str, Any]:
    """Map a discovered+enriched AWS row into the normalized `resources` schema."""
    service = row["service"]
    resource_type = row["resource_type"]

    mapped: dict[str, Any] = {
        "provider": Provider.AWS,
        # Lowercased at write time, same convention Task 18 established for
        # Azure - ARNs are typically stable-case, but there's no reason to
        # reintroduce that bug class rather than reusing the fix.
        "external_resource_id": row["arn"].lower(),
        "name": row["tags"].get("Name"),
        # Machine-readable identifier for resource_type filtering on /cost and
        # /forecast, mirroring Azure's lowercase "microsoft.compute/..." style -
        # adopted AWS's own CloudFormation/Config "AWS::Service::Type" naming
        # (lowercased) since it's the convention AWS users already recognize,
        # rather than inventing a slash-separated Azure-style equivalent.
        "resource_type": f"aws::{service}::{resource_type or 'resource'}",
        "region": row.get("region"),
        # GOV-002 Section 3's resolved decision: the *human-readable resource
        # type* (e.g. "EC2 instance"), not an Azure-style resource group - AWS
        # has no equivalent concept. This is what the drill-down UI's middle
        # level renders verbatim as a section heading, so it's kept readable
        # rather than a raw "AWS::EC2::Instance" CloudFormation-style string.
        "resource_group": _resource_type_label(service, resource_type),
        "tags": row["tags"],
        "sku": row.get("instance_type") or row.get("volume_type"),
        "raw_metadata": row,
    }
    if row.get("created_at") is not None:
        created_at = row["created_at"]
        # boto3 already returns real datetime objects (unlike Azure Resource
        # Graph's ISO-8601 strings) - only normalize if a test/fixture passed a
        # string instead.
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        mapped["created_at"] = created_at
    return mapped


def get_or_create_aws_cloud_account(db: Session, account_id: str) -> CloudAccount:
    account = db.query(CloudAccount).filter_by(provider=Provider.AWS, external_id=account_id).one_or_none()
    if account is None:
        account = CloudAccount(
            provider=Provider.AWS,
            external_id=account_id,
            display_name=f"AWS Account {account_id}",
        )
        db.add(account)
        db.flush()
    return account


def upsert_resources(db: Session, cloud_account: CloudAccount, mapped_resources: list[dict[str, Any]]) -> tuple[int, int]:
    """Mirrors azure_inventory.upsert_resources exactly (including Task 18's
    case-insensitive-by-normalization fix) - kept as its own copy rather than a
    cross-import from azure_inventory, so this module stays a self-contained,
    independently-readable provider connector matching azure_inventory.py's own
    shape, at the cost of duplicating ~15 lines. Worth revisiting as a shared
    helper if a third provider ever needs the exact same logic again."""
    created = 0
    updated = 0
    for mapped in mapped_resources:
        existing = db.query(Resource).filter_by(external_resource_id=mapped["external_resource_id"]).one_or_none()
        if existing is None:
            db.add(Resource(cloud_account_id=cloud_account.id, **mapped))
            created += 1
        else:
            for key, value in mapped.items():
                setattr(existing, key, value)
            updated += 1
    db.commit()
    return created, updated


def sync_aws_inventory(
    db: Session, fetch: Callable[[str], list[dict[str, Any]]] = fetch_resources
) -> SyncSummary:
    region = settings.aws_region
    raw_resources = fetch(region)
    cloud_account = get_or_create_aws_cloud_account(db, settings.aws_account_id)
    mapped_resources = [map_resource(row) for row in raw_resources]
    created, updated = upsert_resources(db, cloud_account, mapped_resources)
    return SyncSummary(found=len(raw_resources), created=created, updated=updated)
