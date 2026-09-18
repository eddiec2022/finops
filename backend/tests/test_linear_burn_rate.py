from datetime import date

from app.services.forecasting.base import ForecastPoint
from app.services.forecasting.linear_burn_rate import LinearBurnRateModel


def test_forecast_computes_average_over_trailing_window():
    model = LinearBurnRateModel(trailing_window_days=2)
    daily_costs = [
        (date(2026, 9, 1), 10.0),
        (date(2026, 9, 2), 20.0),
        (date(2026, 9, 3), 30.0),
    ]

    result = model.forecast(daily_costs, horizon_days=3)

    assert result.insufficient_data is False
    assert result.daily_rate == 25.0  # average of the last 2 days: (20 + 30) / 2
    assert [p.date for p in result.points] == [date(2026, 9, 4), date(2026, 9, 5), date(2026, 9, 6)]
    assert all(p.projected_cost == 25.0 for p in result.points)


def test_forecast_uses_all_available_history_when_shorter_than_window():
    model = LinearBurnRateModel(trailing_window_days=30)
    daily_costs = [(date(2026, 9, 1), 10.0), (date(2026, 9, 2), 20.0)]

    result = model.forecast(daily_costs, horizon_days=1)

    assert result.daily_rate == 15.0  # average of both available days, not divided by 30
    assert result.insufficient_data is False
    assert result.points == [ForecastPoint(date=date(2026, 9, 3), projected_cost=15.0)]


def test_forecast_sorts_unsorted_input_before_windowing():
    model = LinearBurnRateModel(trailing_window_days=2)
    daily_costs = [
        (date(2026, 9, 3), 30.0),
        (date(2026, 9, 1), 10.0),
        (date(2026, 9, 2), 20.0),
    ]

    result = model.forecast(daily_costs, horizon_days=1)

    assert result.daily_rate == 25.0
    assert result.points[0].date == date(2026, 9, 4)


def test_forecast_zero_historical_data_returns_insufficient_data_indicator():
    model = LinearBurnRateModel(trailing_window_days=30)

    result = model.forecast([], horizon_days=90)

    assert result.insufficient_data is True
    assert result.daily_rate is None
    assert result.points == []


def test_forecast_zero_fills_gap_days_within_the_calendar_window():
    # A resource with a gap in its cost history (powered off, then resumed) has
    # no cost_records row at all for the gap days. Windowing by calendar days
    # (not "last N entries") means the window still spans exactly
    # trailing_window_days, and the missing days count as $0, not as if they
    # didn't exist.
    model = LinearBurnRateModel(trailing_window_days=5)
    daily_costs = [
        (date(2026, 9, 1), 100.0),  # old heavy usage, well outside the 5-day window
        (date(2026, 9, 10), 10.0),  # only day with data inside the window
        # 2026-09-06 .. 2026-09-09 have no cost record at all - real $0 days
    ]

    result = model.forecast(daily_costs, horizon_days=1)

    # Window is [09-06, 09-10] (5 calendar days ending on the most recent date).
    # (0 + 0 + 0 + 0 + 10) / 5 = 2.0 - the old 09-01 spike is correctly excluded
    # since it falls outside the window, not averaged in via entry-count slicing.
    assert result.daily_rate == 2.0
    assert result.points == [ForecastPoint(date=date(2026, 9, 11), projected_cost=2.0)]


def test_forecast_gap_older_than_window_does_not_shrink_window_length():
    # Same shape as the real Task 7 finding: a resource has history older than
    # the window, then a gap, then recent activity. The window must still be
    # exactly trailing_window_days calendar days (zero-filling the gap),
    # not len(actual entries inside that span).
    model = LinearBurnRateModel(trailing_window_days=30)
    daily_costs = [
        (date(2026, 7, 1), 10.776) for _ in range(1)
    ] + [
        (date(2026, 9, 15), 2.207597),
        (date(2026, 9, 16), 1.810992),
        (date(2026, 9, 17), 0.583703),
    ]

    result = model.forecast(daily_costs, horizon_days=1)

    # Window is the 30 calendar days ending 2026-09-17 (2026-08-19 .. 2026-09-17).
    # 2026-07-01 falls outside it and must not be counted.
    window_sum = 2.207597 + 1.810992 + 0.583703
    assert result.daily_rate == window_sum / 30
