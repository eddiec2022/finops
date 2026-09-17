from datetime import datetime, timezone
from types import SimpleNamespace

T0 = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 17, 1, 0, tzinfo=timezone.utc)


def _point(timestamp, average):
    return SimpleNamespace(timestamp=timestamp, average=average)


def _timeseries(*points):
    return SimpleNamespace(data=list(points))


def _metric(name, unit, *timeseries):
    return SimpleNamespace(name=name, unit=unit, timeseries=list(timeseries))


def _response(*metrics):
    return SimpleNamespace(metrics=list(metrics))


VM_CPU_RESPONSE = _response(
    _metric("Percentage CPU", "Percent", _timeseries(_point(T0, 12.5), _point(T1, 8.3)))
)

VM_MEMORY_RESPONSE = _response(
    _metric("Available Memory Bytes", "Bytes", _timeseries(_point(T0, 1073741824.0)))
)

VM_DISK_READ_RESPONSE = _response(_metric("Disk Read Bytes", "Bytes", _timeseries(_point(T0, 4096.0))))

VM_DISK_WRITE_RESPONSE = _response(_metric("Disk Write Bytes", "Bytes", _timeseries(_point(T0, 2048.0))))

VM_NETWORK_IN_RESPONSE = _response(_metric("Network In Total", "Bytes", _timeseries(_point(T0, 500.0))))

VM_NETWORK_OUT_RESPONSE = _response(_metric("Network Out Total", "Bytes", _timeseries(_point(T0, 250.0))))

APP_SERVICE_CPU_RESPONSE = _response(
    _metric("CpuPercentage", "Percent", _timeseries(_point(T0, 22.1)))
)

APP_SERVICE_MEMORY_RESPONSE = _response(
    _metric("MemoryPercentage", "Percent", _timeseries(_point(T0, 55.0)))
)

APP_SERVICE_BYTES_RECEIVED_RESPONSE = _response(
    _metric("BytesReceived", "Bytes", _timeseries(_point(T0, 10240.0)))
)

APP_SERVICE_BYTES_SENT_RESPONSE = _response(
    _metric("BytesSent", "Bytes", _timeseries(_point(T0, 8192.0)))
)

# A response with a data point present but no aggregated value yet (a gap in the
# series) - should be skipped, not stored as a null/zero reading.
RESPONSE_WITH_GAP = _response(
    _metric("Percentage CPU", "Percent", _timeseries(_point(T0, 12.5), _point(T1, None)))
)
