import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockFetchResponses } from "../testUtils";
import { Recommendations } from "./Recommendations";

const RIGHTSIZING = "/api/v1/recommendations/rightsizing";
const IDLE = "/api/v1/recommendations/idle-resources";
const NON_PEAK = "/api/v1/recommendations/non-peak-scheduling";
const RESERVED_INSTANCES = "/api/v1/recommendations/reserved-instances";

const EMPTY_RIGHTSIZING = { idle_cpu_threshold_percent: 10, idle_lookback_days: 14, recommendations: [] };
const EMPTY_IDLE = { idle_lookback_days: 14, recommendations: [] };
const EMPTY_NON_PEAK = {
  idle_lookback_days: 14,
  off_peak_usage_ratio_threshold: 0.5,
  business_hours_definition: "Fixed weekday 09:00-17:00 UTC window.",
  recommendations: [],
};
const EMPTY_RI = {
  source: "Azure Microsoft.Consumption reservationRecommendations API",
  field_mapping_note: "Unverified against real populated data.",
  recommendations: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Recommendations", () => {
  it("groups recommendations by category and shows a per-category empty note where there's nothing", async () => {
    mockFetchResponses({
      [RIGHTSIZING]: EMPTY_RIGHTSIZING,
      [IDLE]: EMPTY_IDLE,
      [NON_PEAK]: {
        ...EMPTY_NON_PEAK,
        recommendations: [
          {
            resource_id: "r4",
            external_resource_id: "/subscriptions/.../vm-dev",
            resource_type: "microsoft.compute/virtualmachines",
            resource_group: "nise-rg",
            region: "eastus",
            signals: {
              tag: { matched: false, detail: "no environment-indicating tag found" },
              naming: { matched: true, detail: "resource name contains 'dev'" },
              usage_pattern: {
                matched: false,
                detail: "Only 3 day(s) of history against a 14-day window.",
                peak_avg_cpu_percent: null,
                off_peak_avg_cpu_percent: null,
              },
            },
            recommended_schedule: "Standard template.",
            estimated_monthly_savings: 6.93,
            savings_note: "Approximate, not a billing quote.",
          },
        ],
      },
      [RESERVED_INSTANCES]: EMPTY_RI,
    });

    render(<Recommendations />);

    await waitFor(() => expect(screen.getByText("vm-dev")).toBeInTheDocument());
    expect(screen.getByText("$6.93", { exact: false })).toBeInTheDocument();
    // Categories with nothing flagged still show their own empty note, not silence.
    expect(screen.getAllByText(/no recommendations in this category right now/i)).toHaveLength(3);
    expect(screen.queryByText(/nothing to flag right now/i)).not.toBeInTheDocument();
  });

  it("shows the overall empty state only when every category is genuinely empty", async () => {
    mockFetchResponses({
      [RIGHTSIZING]: EMPTY_RIGHTSIZING,
      [IDLE]: EMPTY_IDLE,
      [NON_PEAK]: EMPTY_NON_PEAK,
      [RESERVED_INSTANCES]: EMPTY_RI,
    });

    render(<Recommendations />);

    await waitFor(() => expect(screen.getByText(/nothing to flag right now/i)).toBeInTheDocument());
    expect(screen.queryByText(/no recommendations in this category right now/i)).not.toBeInTheDocument();
  });

  it("degrades one category independently when its fetch fails, without blanking the others", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes(RIGHTSIZING)) {
          return Promise.reject(new Error("network error"));
        }
        const body = url.includes(IDLE)
          ? EMPTY_IDLE
          : url.includes(NON_PEAK)
            ? EMPTY_NON_PEAK
            : url.includes(RESERVED_INSTANCES)
              ? EMPTY_RI
              : null;
        if (!body) {
          return Promise.reject(new Error(`Unexpected fetch to ${url}`));
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
      }),
    );

    render(<Recommendations />);

    await waitFor(() => expect(screen.getByText(/couldn't load recommendations for this category/i)).toBeInTheDocument());
    // The other three categories still rendered their own (empty) state, not swallowed by the failure.
    expect(screen.getAllByText(/no recommendations in this category right now/i)).toHaveLength(3);
  });
});
