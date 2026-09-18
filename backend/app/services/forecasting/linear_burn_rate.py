from datetime import date, timedelta

from app.core.config import settings
from app.services.forecasting.base import ForecastModel, ForecastPoint, ForecastResult


class LinearBurnRateModel(ForecastModel):
    """v1 forecast model: flat average daily cost over a trailing window,
    projected forward at that constant rate. Deliberately not regression/trend
    fitting - the simplest sensible baseline, per the "start simple" decision.
    """

    def __init__(self, trailing_window_days: int | None = None):
        self.trailing_window_days = (
            trailing_window_days if trailing_window_days is not None else settings.forecast_trailing_window_days
        )

    def forecast(self, daily_costs: list[tuple[date, float]], horizon_days: int) -> ForecastResult:
        if not daily_costs:
            return ForecastResult(points=[], daily_rate=None, insufficient_data=True)

        cost_by_date: dict[date, float] = {}
        for day, cost in daily_costs:
            cost_by_date[day] = cost_by_date.get(day, 0.0) + cost

        earliest_date = min(cost_by_date)
        most_recent_date = max(cost_by_date)

        # Window by calendar days ending on the most recent date with data, not
        # by slicing the last N *entries* - a resource with a gap in its cost
        # history (powered off, then resumed) has no cost_records row at all for
        # the gap days, and slicing by entry count would silently reach back
        # past the gap into stale, older pricing. Bounded below by earliest_date
        # so a resource with less history than the window still averages over
        # just what actually exists, rather than diluting it with zero-filled
        # days from before the resource had any data at all.
        if self.trailing_window_days > 0:
            window_start = max(most_recent_date - timedelta(days=self.trailing_window_days - 1), earliest_date)
        else:
            window_start = earliest_date
        window_length = (most_recent_date - window_start).days + 1

        # Days inside the window with no cost record are real information (zero
        # cost that day), not missing data - zero-filled rather than skipped.
        daily_rate = (
            sum(cost_by_date.get(window_start + timedelta(days=offset), 0.0) for offset in range(window_length))
            / window_length
        )

        points = [
            ForecastPoint(date=most_recent_date + timedelta(days=offset), projected_cost=daily_rate)
            for offset in range(1, horizon_days + 1)
        ]
        return ForecastResult(points=points, daily_rate=daily_rate, insufficient_data=False)
