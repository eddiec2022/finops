import type { CostHistoryResponse } from "../api/types";

export interface TrailingSpend {
  /** Actual calendar days the window covers - min(days, the series' own span) - always matches `total`'s window. */
  windowDays: number;
  total: number;
}

export const EMPTY_TRAILING_SPEND: TrailingSpend = { windowDays: 0, total: 0 };

/**
 * Sums actual_cost within the trailing `days` calendar days, anchored on the
 * *data's own latest date*, not "today" - not an array slice.
 *
 * Task 21 fix: `history.series` only has a row for a date with an actual
 * cost_record (backend/app/services/forecast.py's GROUP BY) - a sync gap or a
 * genuinely zero-cost day is simply absent, not present with a zero value. The
 * old `series.slice(-days)` took the last N *array entries*, which silently
 * reaches further back in time than N calendar days whenever a gap exists
 * anywhere in the window - the UI's own "last 30 days" label became
 * inaccurate with no visible indication. Filtering by an actual date cutoff
 * fixes that.
 *
 * Anchored on the series' latest date rather than the browser's current date,
 * deliberately: synced data can lag real "today" by however long it's been
 * since the last sync, and anchoring on real "today" would make a resource's
 * own most-recently-synced days look like a gap rather than "not synced yet".
 * This mirrors LinearBurnRateModel's identical choice server-side
 * (forecasting/linear_burn_rate.py: "Window by calendar days ending on the
 * most recent date with data, not... by slicing the last N entries") - same
 * principle, now applied consistently on both sides of this exact split.
 */
export function sumTrailingActual(history: CostHistoryResponse, days: number): TrailingSpend {
  if (history.series.length === 0) return EMPTY_TRAILING_SPEND;

  const earliest = history.series[0].date;
  const latest = history.series[history.series.length - 1].date;
  const spanDays = Math.round((Date.parse(latest) - Date.parse(earliest)) / 86_400_000) + 1;
  const windowDays = Math.min(days, spanDays);

  const cutoff = new Date(latest);
  cutoff.setUTCDate(cutoff.getUTCDate() - (windowDays - 1));
  const cutoffDate = cutoff.toISOString().slice(0, 10);

  const total = history.series
    .filter((point) => point.date >= cutoffDate)
    .reduce((sum, point) => sum + point.actual_cost, 0);

  return { windowDays, total };
}
