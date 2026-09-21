"""Pre-merged AWS resource rows - the shape aws_inventory.fetch_resources()
produces internally after combining Tagging API discovery with describe_*
enrichment, and what map_resource() actually consumes directly (mirrors how
azure_resource_graph.py's rows represent azure_inventory.map_resource's input
shape - the difference is AWS's fetch needs two real API calls merged into this
shape first, where Azure's Resource Graph query already returns it in one)."""

from datetime import datetime, timezone

# created_at is an ISO string here, matching what fetch_resources' enrichment
# actually produces (not a raw datetime - see aws_inventory._enrich_ec2_instances'
# comment on why: raw_metadata stores this whole row as-is into a JSONB column,
# and a bare datetime isn't JSON-serializable).
EC2_INSTANCE_ROW = {
    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
    "service": "ec2",
    "region": "us-east-1",
    "account_id": "123456789012",
    "resource_type": "instance",
    "resource_id": "i-0123456789abcdef0",
    "tags": {"Name": "web-01", "env": "prod"},
    "instance_type": "t3.micro",
    "created_at": datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
}

EBS_VOLUME_ROW = {
    "arn": "arn:aws:ec2:us-east-1:123456789012:volume/vol-0123456789abcdef0",
    "service": "ec2",
    "region": "us-east-1",
    "account_id": "123456789012",
    "resource_type": "volume",
    "resource_id": "vol-0123456789abcdef0",
    "tags": {"env": "prod"},
    "volume_type": "gp3",
    "created_at": datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc).isoformat(),
}

# S3 bucket ARNs have no region/account-id segment at all (parse_arn's real
# API-shape finding), and this bucket has no describe_*-equivalent enrichment
# call in v1 - no instance_type/volume_type/created_at.
S3_BUCKET_ROW = {
    "arn": "arn:aws:s3:::my-finops-bucket",
    "service": "s3",
    "region": None,
    "account_id": None,
    "resource_type": None,
    "resource_id": "my-finops-bucket",
    "tags": {},
}

# An untagged-for-a-label resource type - not in _RESOURCE_TYPE_LABELS, exercises
# the generic humanized fallback.
UNLISTED_TYPE_ROW = {
    "arn": "arn:aws:rds:us-east-1:123456789012:db/prod-database-1",
    "service": "rds",
    "region": "us-east-1",
    "account_id": "123456789012",
    "resource_type": "db",
    "resource_id": "prod-database-1",
    "tags": {"Name": "prod-db"},
}
