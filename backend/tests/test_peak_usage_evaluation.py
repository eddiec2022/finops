from datetime import datetime, timedelta, timezone

from app.services.peak_usage_evaluation import evaluate_peak_off_peak_usage, is_business_hours

# 2026-09-14 is a Monday.
MONDAY = datetime(2026, 9, 14, tzinfo=timezone.utc)


def test_is_business_hours_weekday_inside_window():
    assert is_business_hours(MONDAY.replace(hour=8)) is True  # window start, inclusive
    assert is_business_hours(MONDAY.replace(hour=13)) is True
    assert is_business_hours(MONDAY.replace(hour=17)) is True  # last hour inside


def test_is_business_hours_weekday_outside_window():
    assert is_business_hours(MONDAY.replace(hour=7)) is False  # just before
    assert is_business_hours(MONDAY.replace(hour=18)) is False  # window end, exclusive
    assert is_business_hours(MONDAY.replace(hour=23)) is False


def test_is_business_hours_weekend_is_never_business_hours():
    saturday = MONDAY + timedelta(days=5)
    sunday = MONDAY + timedelta(days=6)
    assert is_business_hours(saturday.replace(hour=12)) is False
    assert is_business_hours(sunday.replace(hour=12)) is False


def _daily_readings(start: datetime, days: int, hour: int, value: float) -> list[tuple[datetime, float]]:
    return [(start.replace(hour=hour) + timedelta(days=d), value) for d in range(days)]


def _weekday_readings(start: datetime, days: int, hour: int, value: float) -> list[tuple[datetime, float]]:
    """Like _daily_readings, but skips weekends - for building "peak" streams
    without leaking a weekend reading at a business-hours clock time into the
    off-peak bucket (weekends are off-peak regardless of hour)."""
    return [
        (start.replace(hour=hour) + timedelta(days=d), value)
        for d in range(days)
        if (start + timedelta(days=d)).weekday() < 5
    ]


def test_evaluate_peak_off_peak_usage_flags_business_app_pattern():
    # Busy during business hours, quiet at night, over a full 14-day window
    # (2 weeks) so both weekday and weekend off-peak readings exist.
    start = MONDAY
    peak_readings = _weekday_readings(start, days=14, hour=13, value=80.0)
    off_peak_readings = _daily_readings(start, days=14, hour=2, value=5.0)

    result = evaluate_peak_off_peak_usage(peak_readings + off_peak_readings, lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.insufficient_data is False
    assert result.peak_avg_cpu_percent == 80.0
    assert result.off_peak_avg_cpu_percent == 5.0
    assert result.is_flagged is True


def test_evaluate_peak_off_peak_usage_does_not_flag_always_busy_resource():
    start = MONDAY
    readings = _weekday_readings(start, days=14, hour=13, value=70.0) + _daily_readings(start, days=14, hour=2, value=65.0)

    result = evaluate_peak_off_peak_usage(readings, lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.insufficient_data is False
    assert result.is_flagged is False


def test_evaluate_peak_off_peak_usage_ratio_boundary_is_inclusive():
    start = MONDAY
    readings = _weekday_readings(start, days=14, hour=13, value=10.0) + _daily_readings(start, days=14, hour=2, value=5.0)

    # off-peak/peak == 0.5 exactly, threshold 0.5 - flags (<=, not strictly <).
    result = evaluate_peak_off_peak_usage(readings, lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.is_flagged is True


def test_evaluate_peak_off_peak_usage_zero_peak_is_not_flagged():
    # Idle around the clock - peak avg is 0, so the ratio isn't meaningful;
    # this is rightsizing's territory, not a peak/off-peak pattern.
    start = MONDAY
    readings = _daily_readings(start, days=14, hour=13, value=0.0) + _daily_readings(start, days=14, hour=2, value=0.0)

    result = evaluate_peak_off_peak_usage(readings, lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.insufficient_data is False
    assert result.is_flagged is False


def test_evaluate_peak_off_peak_usage_insufficient_history_excludes_not_flags():
    start = MONDAY
    # Only 3 days against a 14-day window, even though the pattern is a
    # textbook business-hours dip.
    readings = _daily_readings(start, days=3, hour=13, value=90.0) + _daily_readings(start, days=3, hour=2, value=1.0)

    result = evaluate_peak_off_peak_usage(readings, lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.insufficient_data is True
    assert result.is_flagged is False
    assert result.peak_avg_cpu_percent is None


def test_evaluate_peak_off_peak_usage_no_readings_is_insufficient_data():
    result = evaluate_peak_off_peak_usage([], lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.insufficient_data is True
    assert result.is_flagged is False


def test_evaluate_peak_off_peak_usage_missing_one_bucket_is_insufficient_data():
    # 14 calendar days of history, but every reading is a weekday business-hour
    # timestamp - no night or weekend readings at all, so the off-peak bucket
    # is empty and the comparison can't be made.
    start = MONDAY
    readings = [
        (start.replace(hour=13) + timedelta(days=d), 50.0)
        for d in range(14)
        if (start + timedelta(days=d)).weekday() < 5
    ]

    result = evaluate_peak_off_peak_usage(readings, lookback_days=14, off_peak_ratio_threshold=0.5)

    assert result.insufficient_data is True
