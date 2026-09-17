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

        sorted_costs = sorted(daily_costs, key=lambda item: item[0])
        # Slicing with a window larger than the available history just returns
        # everything - "use whatever exists" for a partial trailing window.
        window = sorted_costs[-self.trailing_window_days :] if self.trailing_window_days > 0 else sorted_costs
        daily_rate = sum(cost for _, cost in window) / len(window)

        last_date = sorted_costs[-1][0]
        points = [
            ForecastPoint(date=last_date + timedelta(days=offset), projected_cost=daily_rate)
            for offset in range(1, horizon_days + 1)
        ]
        return ForecastResult(points=points, daily_rate=daily_rate, insufficient_data=False)
