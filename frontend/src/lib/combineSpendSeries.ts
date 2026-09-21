import type { CostHistoryPoint, ForecastPoint } from "../api/types";

export interface SpendChartPoint {
  date: string;
  actual?: number;
  projected?: number;
}

/**
 * Merges actual daily-cost history with the projected forecast series into a
 * single chart-ready array. The last actual point also carries the same value
 * under `projected` so the dashed line starts exactly where the solid line
 * ends, instead of leaving a visual gap between "last known day" and "first
 * projected day".
 */
export function combineSpendSeries(history: CostHistoryPoint[], forecast: ForecastPoint[]): SpendChartPoint[] {
  const points: SpendChartPoint[] = history.map((point) => ({ date: point.date, actual: point.actual_cost }));

  if (points.length > 0 && forecast.length > 0) {
    const last = points[points.length - 1];
    points[points.length - 1] = { ...last, projected: last.actual };
  }

  for (const point of forecast) {
    points.push({ date: point.date, projected: point.projected_cost });
  }

  return points;
}
