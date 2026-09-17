from azure.core.exceptions import HttpResponseError

from app.models.cloud_account import CloudAccount
from app.models.provider import Provider
from app.models.resource import Resource
from app.models.utilization_metric import UtilizationMetric
from app.services.azure_utilization import (
    RESOURCE_TYPE_METRICS,
    fetch_metrics,
    map_metric_response,
    sync_utilization,
)
from tests.fixtures.azure_monitor import (
    APP_SERVICE_BYTES_RECEIVED_RESPONSE,
    APP_SERVICE_BYTES_SENT_RESPONSE,
    APP_SERVICE_CPU_RESPONSE,
    APP_SERVICE_MEMORY_RESPONSE,
    RESPONSE_WITH_GAP,
    T0,
    T1,
    VM_CPU_RESPONSE,
    VM_DISK_READ_RESPONSE,
    VM_DISK_WRITE_RESPONSE,
    VM_MEMORY_RESPONSE,
    VM_NETWORK_IN_RESPONSE,
    VM_NETWORK_OUT_RESPONSE,
)


def test_map_metric_response_flattens_timeseries():
    rows = map_metric_response(VM_CPU_RESPONSE)

    assert rows == [
        {"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T0, "value": 12.5},
        {"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T1, "value": 8.3},
    ]


def test_map_metric_response_skips_missing_average():
    rows = map_metric_response(RESPONSE_WITH_GAP)

    assert rows == [{"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T0, "value": 12.5}]


def test_fetch_metrics_vm_with_all_metrics_present():
    responses = {
        "Percentage CPU": VM_CPU_RESPONSE,
        "Available Memory Bytes": VM_MEMORY_RESPONSE,
        "Disk Read Bytes": VM_DISK_READ_RESPONSE,
        "Disk Write Bytes": VM_DISK_WRITE_RESPONSE,
        "Network In Total": VM_NETWORK_IN_RESPONSE,
        "Network Out Total": VM_NETWORK_OUT_RESPONSE,
    }

    def fake_query_metric(resource_uri, metric_name, lookback_days):
        return responses[metric_name]

    rows = fetch_metrics(
        "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
        list(responses.keys()),
        14,
        query_metric=fake_query_metric,
    )

    metric_names_found = {row["metric_name"] for row in rows}
    assert metric_names_found == set(responses.keys())
    assert len(rows) == 7  # CPU has 2 points, the other five have 1 each


def test_fetch_metrics_vm_with_memory_missing_does_not_error():
    def fake_query_metric(resource_uri, metric_name, lookback_days):
        if metric_name == "Available Memory Bytes":
            raise HttpResponseError(message="the metric names Available Memory Bytes are not supported")
        return VM_CPU_RESPONSE

    rows = fetch_metrics(
        "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-2",
        ["Percentage CPU", "Available Memory Bytes"],
        14,
        query_metric=fake_query_metric,
    )

    metric_names_found = {row["metric_name"] for row in rows}
    assert metric_names_found == {"Percentage CPU"}
    assert "Available Memory Bytes" not in metric_names_found


def test_fetch_metrics_app_service():
    responses = {
        "CpuPercentage": APP_SERVICE_CPU_RESPONSE,
        "MemoryPercentage": APP_SERVICE_MEMORY_RESPONSE,
        "BytesReceived": APP_SERVICE_BYTES_RECEIVED_RESPONSE,
        "BytesSent": APP_SERVICE_BYTES_SENT_RESPONSE,
    }

    def fake_query_metric(resource_uri, metric_name, lookback_days):
        return responses[metric_name]

    rows = fetch_metrics(
        "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Web/sites/app-1",
        list(responses.keys()),
        14,
        query_metric=fake_query_metric,
    )

    metric_names_found = {row["metric_name"] for row in rows}
    assert metric_names_found == set(responses.keys())
    assert len(rows) == 4


def _seed_vm(db_session) -> Resource:
    account = CloudAccount(provider=Provider.AZURE, external_id="sub-1", display_name="Test Sub")
    db_session.add(account)
    db_session.flush()
    vm = Resource(
        cloud_account_id=account.id,
        provider=Provider.AZURE,
        external_resource_id="/subscriptions/x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
        resource_type="microsoft.compute/virtualmachines",
        tags={},
        raw_metadata={},
    )
    db_session.add(vm)
    db_session.commit()
    return vm


def test_sync_utilization_creates_metrics(db_session):
    # Scoped to this test's own VM and metric rows, not absolute counts - the dev
    # DB this suite runs against also carries real compute resources from live-run
    # verification (see README), so other resources may legitimately get processed
    # too.
    before_processed = (
        db_session.query(Resource).filter(Resource.resource_type.in_(RESOURCE_TYPE_METRICS.keys())).count()
    )
    vm = _seed_vm(db_session)

    def fake_fetch(resource_uri, metric_names, lookback_days):
        if resource_uri != vm.external_resource_id:
            return []
        return [{"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T0, "value": 12.5}]

    summary = sync_utilization(db_session, fetch=fake_fetch)

    assert summary.resources_processed == before_processed + 1
    assert summary.metrics_found == 1
    assert summary.created == 1
    assert summary.updated == 0
    assert db_session.query(UtilizationMetric).filter_by(resource_id=vm.id).count() == 1


def test_sync_utilization_upsert_does_not_duplicate_on_overlapping_window(db_session):
    vm = _seed_vm(db_session)

    def fake_fetch(resource_uri, metric_names, lookback_days):
        if resource_uri != vm.external_resource_id:
            return []
        return [
            {"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T0, "value": 12.5},
            {"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T1, "value": 8.3},
        ]

    sync_utilization(db_session, fetch=fake_fetch)

    def fake_fetch_overlapping(resource_uri, metric_names, lookback_days):
        if resource_uri != vm.external_resource_id:
            return []
        return [
            {"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T0, "value": 99.0},
            {"metric_name": "Percentage CPU", "unit": "Percent", "timestamp": T1, "value": 8.3},
        ]

    summary = sync_utilization(db_session, fetch=fake_fetch_overlapping)

    assert summary.created == 0
    assert summary.updated == 2
    assert db_session.query(UtilizationMetric).filter_by(resource_id=vm.id).count() == 2

    updated_point = (
        db_session.query(UtilizationMetric)
        .filter_by(resource_id=vm.id, metric_name="Percentage CPU", timestamp=T0)
        .one()
    )
    assert updated_point.value == 99.0


def test_sync_utilization_skips_non_compute_resource_types(db_session):
    account = CloudAccount(provider=Provider.AZURE, external_id="sub-1", display_name="Test Sub")
    db_session.add(account)
    db_session.flush()
    storage_resource_uri = "/subscriptions/x/.../storageAccounts/sa1"
    db_session.add(
        Resource(
            cloud_account_id=account.id,
            provider=Provider.AZURE,
            external_resource_id=storage_resource_uri,
            resource_type="microsoft.storage/storageaccounts",
            tags={},
            raw_metadata={},
        )
    )
    db_session.commit()
    before_processed = (
        db_session.query(Resource).filter(Resource.resource_type.in_(RESOURCE_TYPE_METRICS.keys())).count()
    )

    def fake_fetch(resource_uri, metric_names, lookback_days):
        if resource_uri == storage_resource_uri:
            raise AssertionError("fetch should not be called for non-compute resource types")
        return []

    summary = sync_utilization(db_session, fetch=fake_fetch)

    # The storage account was never queried (fake_fetch would have raised);
    # resources_processed reflects only whatever compute/App Service resources
    # already existed, unaffected by the (correctly skipped) storage account.
    assert summary.resources_processed == before_processed
    assert summary.metrics_found == 0
