from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class ForecastPoint:
    date: date
    projected_cost: float


@dataclass
class ForecastResult:
    points: list[ForecastPoint]
    daily_rate: float | None
    insufficient_data: bool


class ForecastModel(ABC):
    """Pluggable forecasting interface.

    Phase 2 (Prophet/ARIMA/ML, with confidence intervals) implements this same
    contract so the endpoint that calls it never has to change - only the model
    passed in does.
    """

    @abstractmethod
    def forecast(self, daily_costs: list[tuple[date, float]], horizon_days: int) -> ForecastResult:
        """Project cost forward `horizon_days` days from a historical daily-cost series.

        `daily_costs` need not be pre-sorted or deduplicated. Returns a
        ForecastResult with insufficient_data=True (empty points, daily_rate=None)
        when there's no historical data to forecast from - never raises, and
        never returns a zero-cost forecast as if it were a real one.
        """
        raise NotImplementedError
