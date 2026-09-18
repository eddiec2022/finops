from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean

# v1 simplification, stated explicitly rather than buried: a fixed weekday
# business-hours window in UTC, not per-resource timezone detection - there's
# no reliable timezone signal in what Task 2 syncs (no resource-level
# timezone field), so a single fixed window is used for every resource
# regardless of its actual region/timezone.
BUSINESS_HOURS_START_UTC = 8
BUSINESS_HOURS_END_UTC = 18  # exclusive
BUSINESS_DAYS = frozenset(range(5))  # Monday=0 .. Friday=4


def is_business_hours(timestamp: datetime) -> bool:
    return timestamp.weekday() in BUSINESS_DAYS and BUSINESS_HOURS_START_UTC <= timestamp.hour < BUSINESS_HOURS_END_UTC


@dataclass
class PeakOffPeakUsageResult:
    peak_avg_cpu_percent: float | None
    off_peak_avg_cpu_percent: float | None
    insufficient_data: bool
    is_flagged: bool
    detail: str


def evaluate_peak_off_peak_usage(
    readings: list[tuple[datetime, float]],
    lookback_days: int,
    off_peak_ratio_threshold: float,
) -> PeakOffPeakUsageResult:
    """Compare average CPU during business hours (weekday 8am-6pm UTC) against
    nights/weekends, over the trailing `lookback_days` window ending on the
    most recent reading.

    A genuinely different kind of analysis than `evaluate_cpu_utilization`'s
    flat average - this buckets by time-of-day/day-of-week first. Flags a
    resource when off-peak usage is at most `off_peak_ratio_threshold` of
    peak usage (e.g. 0.5 = off-peak is half of peak or less).

    Same "insufficient data -> exclude, don't guess" principle as every other
    recommendation check: too little history, or a window that happens to
    have no readings in one of the two buckets, both return
    insufficient_data=True rather than a partial/misleading comparison. A
    peak average of ~0% is also not flagged via this check (division by a
    near-zero peak isn't a meaningful ratio) - that's an idle-resource
    situation for the rightsizing check to catch, not a peak/off-peak pattern.
    """
    if not readings:
        return PeakOffPeakUsageResult(None, None, True, False, "No utilization data available.")

    timestamps = [ts for ts, _ in readings]
    most_recent = max(timestamps)
    earliest = min(timestamps)
    span_days = (most_recent.date() - earliest.date()).days + 1
    if span_days < lookback_days:
        return PeakOffPeakUsageResult(
            None, None, True, False, f"Only {span_days} day(s) of history against a {lookback_days}-day window."
        )

    window_start_date = most_recent.date() - timedelta(days=lookback_days - 1)
    windowed = [(ts, value) for ts, value in readings if ts.date() >= window_start_date]

    peak_values = [value for ts, value in windowed if is_business_hours(ts)]
    off_peak_values = [value for ts, value in windowed if not is_business_hours(ts)]
    if not peak_values or not off_peak_values:
        return PeakOffPeakUsageResult(
            None, None, True, False, "Window doesn't contain readings in both the peak and off-peak buckets."
        )

    peak_avg = mean(peak_values)
    off_peak_avg = mean(off_peak_values)

    if peak_avg <= 0:
        return PeakOffPeakUsageResult(
            peak_avg,
            off_peak_avg,
            False,
            False,
            "Peak-hours average CPU is ~0%; the peak/off-peak ratio isn't meaningful here.",
        )

    ratio = off_peak_avg / peak_avg
    is_flagged = ratio <= off_peak_ratio_threshold
    comparison = "<=" if is_flagged else ">"
    detail = (
        f"peak avg {peak_avg:.2f}%, off-peak avg {off_peak_avg:.2f}% "
        f"(ratio {ratio:.2f} {comparison} threshold {off_peak_ratio_threshold})"
    )
    return PeakOffPeakUsageResult(peak_avg, off_peak_avg, False, is_flagged, detail)
