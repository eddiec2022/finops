import { describe, expect, it } from "vitest";
import { combineSpendSeries } from "./combineSpendSeries";

describe("combineSpendSeries", () => {
  it("marks historical points as actual and connects the last actual point to the projection", () => {
    const result = combineSpendSeries(
      [
        { date: "2026-09-01", actual_cost: 10 },
        { date: "2026-09-02", actual_cost: 20 },
      ],
      [{ date: "2026-09-03", projected_cost: 15 }],
    );

    expect(result).toEqual([
      { date: "2026-09-01", actual: 10 },
      { date: "2026-09-02", actual: 20, projected: 20 },
      { date: "2026-09-03", projected: 15 },
    ]);
  });

  it("returns only the projected series when there's no actual history", () => {
    const result = combineSpendSeries([], [{ date: "2026-09-03", projected_cost: 15 }]);

    expect(result).toEqual([{ date: "2026-09-03", projected: 15 }]);
  });

  it("returns only the actual series, unmodified, when there's no forecast", () => {
    const result = combineSpendSeries([{ date: "2026-09-01", actual_cost: 10 }], []);

    expect(result).toEqual([{ date: "2026-09-01", actual: 10 }]);
  });
});
