import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const FORECAST_FRAGMENT = "/api/v1/forecast";
const COST_FRAGMENT = "/api/v1/cost";

function mockFetchResponses(responses: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      const matchedKey = Object.keys(responses).find((fragment) => url.includes(fragment));
      if (!matchedKey) {
        return Promise.reject(new Error(`Unexpected fetch to ${url}`));
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(responses[matchedKey]),
      } as Response);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("renders the current-spend figure and chart when real data is available", async () => {
    mockFetchResponses({
      [COST_FRAGMENT]: {
        series: [
          { date: "2026-09-01", actual_cost: 10 },
          { date: "2026-09-02", actual_cost: 20 },
        ],
      },
      [FORECAST_FRAGMENT]: {
        insufficient_data: false,
        daily_rate: 15,
        horizon_days: 90,
        rollups: { "7": 105, "90": 1350 },
        series: [{ date: "2026-09-03", projected_cost: 15 }],
      },
    });

    render(<App />);

    await waitFor(() => expect(screen.getByText("$30.00")).toBeInTheDocument());
    expect(screen.getByText(/spend trend/i)).toBeInTheDocument();
    expect(screen.queryByText(/not enough usage history/i)).not.toBeInTheDocument();
  });

  it("renders the empty state when the forecast reports insufficient data", async () => {
    mockFetchResponses({
      [COST_FRAGMENT]: { series: [] },
      [FORECAST_FRAGMENT]: {
        insufficient_data: true,
        daily_rate: null,
        horizon_days: 90,
        rollups: {},
        series: [],
      },
    });

    render(<App />);

    await waitFor(() => expect(screen.getByText(/not enough usage history/i)).toBeInTheDocument());
    expect(screen.queryByText(/solid = actual/i)).not.toBeInTheDocument();
  });

  it("renders an error message when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network error"))),
    );

    render(<App />);

    await waitFor(() => expect(screen.getByText(/couldn't reach the backend/i)).toBeInTheDocument());
  });
});
