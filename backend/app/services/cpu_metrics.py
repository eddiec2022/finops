# The CPU metric azure_utilization.py stores for each resource type it
# supports - must match RESOURCE_TYPE_METRICS in that module (kept as a
# separate explicit mapping rather than reaching into that list's ordering,
# since "first metric in the sync list" isn't a documented contract).
CPU_METRIC_BY_RESOURCE_TYPE: dict[str, str] = {
    "microsoft.compute/virtualmachines": "Percentage CPU",
    "microsoft.web/sites": "CpuPercentage",
}
