from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CpuUtilizationResult:
    avg_cpu_percent: float | None
    insufficient_data: bool
    is_idle: bool


def evaluate_cpu_utilization(
    readings: list[tuple[datetime, float]],
    lookback_days: int,
    idle_threshold_percent: float,
) -> CpuUtilizationResult:
    """Average CPU% over the trailing `lookback_days` window ending on the most
    recent reading, and flag idleness against `idle_threshold_percent`.

    `readings` need not be sorted. A resource whose earliest reading doesn't
    reach back far enough to cover the full lookback window has
    insufficient_data=True - it must be excluded from results entirely rather
    than flagged (or cleared) on a partial average, mirroring the forecasting
    model's "insufficient data" handling (Task 7/8).
    """
    if not readings:
        return CpuUtilizationResult(avg_cpu_percent=None, insufficient_data=True, is_idle=False)

    timestamps = [ts for ts, _ in readings]
    most_recent = max(timestamps)
    earliest = min(timestamps)
    span_days = (most_recent.date() - earliest.date()).days + 1
    if span_days < lookback_days:
        return CpuUtilizationResult(avg_cpu_percent=None, insufficient_data=True, is_idle=False)

    window_start_date = most_recent.date() - timedelta(days=lookback_days - 1)
    window_values = [value for ts, value in readings if ts.date() >= window_start_date]
    avg_cpu_percent = sum(window_values) / len(window_values)
    return CpuUtilizationResult(
        avg_cpu_percent=avg_cpu_percent,
        insufficient_data=False,
        is_idle=avg_cpu_percent < idle_threshold_percent,
    )
