# The CPU metric aws_utilization.py stores for each resource type it supports -
# must match AWS_RESOURCE_TYPE_METRICS in that module, same "kept as a separate
# explicit mapping" reasoning as cpu_metrics.py. Only EC2 for v1 - GOV-002 2.3
# says "CPUUtilization for EC2, equivalent per-service metrics for other compute
# types as they're added", and no other AWS compute type is in scope yet.
AWS_CPU_METRIC_BY_RESOURCE_TYPE: dict[str, str] = {
    "aws::ec2::instance": "CPUUtilization",
}
