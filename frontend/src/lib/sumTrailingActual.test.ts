import { describe, expect, it } from "vitest";
import type { CostHistoryPoint } from "../api/types";
import { sumTrailingActual } from "./sumTrailingActual";

function point(date: string, actual_cost: number): CostHistoryPoint {
  return { date, actual_cost };
}

/** N consecutive calendar days starting at `startDate`, one point per day - the dense/no-gap case. */
function denseDays(startDate: string, count: number, costPerDay: number): CostHistoryPoint[] {
  const start = new Date(startDate);
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(start);
    d.setUTCDate(d.getUTCDate() + i);
    return point(d.toISOString().slice(0, 10), costPerDay);
  });
}

describe("sumTrailingActual", () => {
  it("returns zero for an empty series", () => {
    expect(sumTrailingActual({ series: [] }, 30)).toEqual({ windowDays: 0, total: 0 });
  });

  it("sums a dense (gap-free) series exactly like the old slice-based logic did", () => {
    // 40 consecutive days, $1/day - last 30 calendar days should be $30, matching
    // the old series.slice(-30) result for this same gap-free case exactly.
    const series = denseDays("2026-08-01", 40, 1);

    const result = sumTrailingActual({ series }, 30);

    expect(result.windowDays).toBe(30);
    expect(result.total).toBe(30);
  });

  it("caps the window to the series' own span when there's less history than requested", () => {
    const series = denseDays("2026-09-01", 10, 2);

    const result = sumTrailingActual({ series }, 30);

    expect(result.windowDays).toBe(10);
    expect(result.total).toBe(20);
  });

  it("Task 21 regression: a gap in the trailing window no longer silently reaches further back than the claimed calendar-day window", () => {
    // The exact scenario the task describes: 35 calendar days of real coverage,
    // but only 25 actual entries (10 zero-cost days in the middle were never
    // written as cost_record rows, so they're simply absent from the series,
    // not present with a zero value).
    const allDays = denseDays("2026-08-01", 35, 3); // $3/day for every real day in the 35-day span
    // Drop days 10-19 (0-indexed) - a 10-day gap in the middle of the window.
    const withGap = [...allDays.slice(0, 10), ...allDays.slice(20)];
    expect(withGap.length).toBe(25); // sanity-check the fixture itself

    const result = sumTrailingActual({ series: withGap }, 30);

    // OLD (buggy) behavior: series.slice(-30) on a 25-entry array returns all
    // 25 entries (since 25 < 30) - claims "last 25 days" via series.length,
    // but actually sums cost spanning the full 35-calendar-day range, quietly
    // reaching 5 days further back than either the label or the 30-day cap
    // claims.
    const oldBuggyLabel = Math.min(30, withGap.length); // 25 - what the old label showed
    const oldBuggySum = withGap.slice(-30).reduce((t, p) => t + p.actual_cost, 0); // sums all 25 entries = $75

    // NEW (fixed) behavior: windowDays correctly reflects the real 30-calendar-day
    // cap (not capped further by entry count), and the sum only includes entries
    // that actually fall within the last 30 calendar days of the 35-day span -
    // excluding the first 5 days of real data, which fall outside that window.
    expect(result.windowDays).toBe(30);
    expect(result.windowDays).not.toBe(oldBuggyLabel);

    // Last 30 calendar days of a 35-day span excludes the first 5 days. Days
    // 0-4 (5 real entries, $3 each = $15) are outside the window; the gap
    // itself (days 10-19) contributes nothing either way since those entries
    // never existed. Remaining real entries inside the window: 25 - 5 = 20,
    // at $3 each = $60.
    expect(result.total).toBe(60);
    expect(result.total).not.toBe(oldBuggySum);
    expect(result.total).toBeLessThan(oldBuggySum);
  });

  it("anchors on the series' own latest date, not the calling environment's current date", () => {
    // Data that stops well before "now" (whatever "now" is when this test
    // runs) must still report a full 30-day window ending on its own last
    // synced date, not look like it has a 30-day gap right before "today".
    const series = denseDays("2020-01-01", 30, 5);

    const result = sumTrailingActual({ series }, 30);

    expect(result.windowDays).toBe(30);
    expect(result.total).toBe(150);
  });
});
