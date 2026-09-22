"""Fake CloudWatch GetMetricStatistics responses - boto3 returns plain dicts,
hand-built to the real shape directly (same convention as fixtures/aws_cost.py)."""

from datetime import datetime, timezone

T0 = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc)

CPU_RESPONSE = {
    "Label": "CPUUtilization",
    "Datapoints": [
        {"Timestamp": T0, "Average": 12.5, "Unit": "Percent"},
        {"Timestamp": T1, "Average": 8.3, "Unit": "Percent"},
    ],
}

# CloudWatch's real behavior for "no data in this window" - an empty
# Datapoints list, not an error (unlike Azure Monitor's HttpResponseError for
# an unsupported metric).
EMPTY_RESPONSE: dict = {"Label": "CPUUtilization", "Datapoints": []}
