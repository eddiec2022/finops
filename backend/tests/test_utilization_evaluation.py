from datetime import datetime, timedelta, timezone

from app.services.utilization_evaluation import evaluate_cpu_utilization


def _hourly_readings(start: datetime, days: int, value: float) -> list[tuple[datetime, float]]:
    return [(start + timedelta(hours=h), value) for h in range(days * 24)]


def test_evaluate_cpu_utilization_flags_clearly_idle_resource():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    readings = _hourly_readings(start, days=14, value=2.0)

    result = evaluate_cpu_utilization(readings, lookback_days=14, idle_threshold_percent=10.0)

    assert result.insufficient_data is False
    assert result.avg_cpu_percent == 2.0
    assert result.is_idle is True


def test_evaluate_cpu_utilization_does_not_flag_clearly_busy_resource():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    readings = _hourly_readings(start, days=14, value=75.0)

    result = evaluate_cpu_utilization(readings, lookback_days=14, idle_threshold_percent=10.0)

    assert result.insufficient_data is False
    assert result.avg_cpu_percent == 75.0
    assert result.is_idle is False


def test_evaluate_cpu_utilization_excludes_resource_with_insufficient_history():
    # Only 3 days of readings against a 14-day lookback window - must be
    # excluded (insufficient_data=True), not flagged on the partial average,
    # even though the 3 days available are clearly idle.
    start = datetime(2026, 9, 15, tzinfo=timezone.utc)
    readings = _hourly_readings(start, days=3, value=1.0)

    result = evaluate_cpu_utilization(readings, lookback_days=14, idle_threshold_percent=10.0)

    assert result.insufficient_data is True
    assert result.avg_cpu_percent is None
    assert result.is_idle is False


def test_evaluate_cpu_utilization_no_readings_at_all_is_insufficient_data():
    result = evaluate_cpu_utilization([], lookback_days=14, idle_threshold_percent=10.0)

    assert result.insufficient_data is True
    assert result.avg_cpu_percent is None
    assert result.is_idle is False


def test_evaluate_cpu_utilization_windows_to_trailing_lookback_only():
    # An old spike outside the lookback window must not pull the average up -
    # only the trailing lookback_days count, mirroring the forecasting
    # model's calendar-window convention.
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    old_spike = _hourly_readings(start, days=1, value=90.0)
    recent_idle = _hourly_readings(start + timedelta(days=13), days=14, value=1.0)

    result = evaluate_cpu_utilization(old_spike + recent_idle, lookback_days=14, idle_threshold_percent=10.0)

    assert result.insufficient_data is False
    assert result.avg_cpu_percent == 1.0
    assert result.is_idle is True


def test_evaluate_cpu_utilization_threshold_is_strict_less_than():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    readings = _hourly_readings(start, days=14, value=10.0)

    result = evaluate_cpu_utilization(readings, lookback_days=14, idle_threshold_percent=10.0)

    assert result.is_idle is False  # avg == threshold, not strictly below it
