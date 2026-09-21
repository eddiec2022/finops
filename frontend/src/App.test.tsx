import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { mockFetchResponses } from "./testUtils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows the Overview page by default and switches to Recommendations via the nav", async () => {
    mockFetchResponses({
      "/api/v1/cost": { series: [] },
      "/api/v1/forecast": { insufficient_data: true, daily_rate: null, horizon_days: 90, rollups: {}, series: [] },
      "/api/v1/recommendations/rightsizing": {
        idle_cpu_threshold_percent: 10,
        idle_lookback_days: 14,
        recommendations: [],
      },
      "/api/v1/recommendations/idle-resources": { idle_lookback_days: 14, recommendations: [] },
      "/api/v1/recommendations/non-peak-scheduling": {
        idle_lookback_days: 14,
        off_peak_usage_ratio_threshold: 0.5,
        business_hours_definition: "Fixed weekday 09:00-17:00 UTC window.",
        recommendations: [],
      },
      "/api/v1/recommendations/reserved-instances": {
        source: "Azure Microsoft.Consumption reservationRecommendations API",
        field_mapping_note: "Unverified against real populated data.",
        recommendations: [],
      },
    });

    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Recommendations" }));

    expect(screen.getByRole("heading", { name: "Recommendations" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/nothing to flag right now/i)).toBeInTheDocument());
  });
});
