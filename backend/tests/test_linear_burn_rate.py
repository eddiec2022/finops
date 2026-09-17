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
