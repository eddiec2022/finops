"""Fake AWS Cost Explorer GetCostAndUsageWithResources responses - boto3 returns
plain dicts (unlike Azure's SDK objects), so these are hand-built to the real
shape directly rather than duck-typed through a helper class."""

INSTANCE_ARN = "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0"

# Cost Explorer's RESOURCE_ID group key casing isn't guaranteed to match what the
# inventory connector stored - used to test the case-insensitive resource match,
# same convention as azure_cost fixtures' VM_RESOURCE_ID_DIFFERENT_CASE.
INSTANCE_ARN_DIFFERENT_CASE = INSTANCE_ARN.upper()


def make_response(*groups_by_day: list[dict]) -> dict:
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-09-15", "End": "2026-09-16"},
                "Groups": groups,
                "Estimated": False,
            }
            for groups in groups_by_day
        ],
    }


def _group(resource_arn: str, record_type: str, amount: str, unit: str = "USD") -> dict:
    return {
        "Keys": [resource_arn, record_type],
        "Metrics": {"AmortizedCost": {"Amount": amount, "Unit": unit}},
    }


RESOURCE_ATTRIBUTABLE_GROUP = _group(INSTANCE_ARN_DIFFERENT_CASE, "Usage", "12.3456")
NON_ATTRIBUTABLE_USAGE_GROUP = _group("", "Usage", "5.00")
NON_ATTRIBUTABLE_TAX_GROUP = _group("", "Tax", "1.25")

RESPONSE_MIXED = make_response([RESOURCE_ATTRIBUTABLE_GROUP, NON_ATTRIBUTABLE_USAGE_GROUP, NON_ATTRIBUTABLE_TAX_GROUP])
