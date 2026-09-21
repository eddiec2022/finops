import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockFetchResponses } from "../testUtils";
import { Overview } from "./Overview";

const FORECAST_FRAGMENT = "/api/v1/forecast";
const COST_FRAGMENT = "/api/v1/cost";
const INVENTORY_FRAGMENT = "/api/v1/inventory";

const EMPTY_FORECAST = { insufficient_data: true, daily_rate: null, horizon_days: 90, rollups: {}, series: [] };
const EMPTY_COST = { series: [] };

const RG_A_VM = {
  resource_id: "res-1",
  external_resource_id: "/subscriptions/x/resourceGroups/rg-a/providers/Microsoft.Compute/virtualMachines/vm-web-01",
  name: "vm-web-01",
  resource_group: "rg-a",
  resource_type: "microsoft.compute/virtualmachines",
  region: "eastus",
};

const RG_A_DISK = {
  resource_id: "res-3",
  external_resource_id: "/subscriptions/x/resourceGroups/rg-a/providers/Microsoft.Compute/disks/vm-web-01-disk",
  name: "vm-web-01-disk",
  resource_group: "rg-a",
  resource_type: "microsoft.compute/disks",
  region: "eastus",
};

const RG_B_STORAGE = {
  resource_id: "res-2",
  external_resource_id: "/subscriptions/x/resourceGroups/rg-b/providers/Microsoft.Storage/storageAccounts/stlogs01",
  name: "stlogs01",
  resource_group: "rg-b",
  resource_type: "microsoft.storage/storageaccounts",
  region: "westus",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Overview", () => {
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
      [INVENTORY_FRAGMENT]: { resources: [RG_A_VM, RG_B_STORAGE] },
    });

    render(<Overview />);

    await waitFor(() => expect(screen.getByText("$30.00")).toBeInTheDocument());
    expect(screen.getByText(/spend trend/i)).toBeInTheDocument();
    expect(screen.queryByText(/not enough usage history/i)).not.toBeInTheDocument();
  });

  it("renders the empty state when the forecast reports insufficient data", async () => {
    mockFetchResponses({
      [COST_FRAGMENT]: EMPTY_COST,
      [FORECAST_FRAGMENT]: EMPTY_FORECAST,
      [INVENTORY_FRAGMENT]: { resources: [] },
    });

    render(<Overview />);

    await waitFor(() => expect(screen.getByText(/not enough usage history/i)).toBeInTheDocument());
    expect(screen.queryByText(/solid = actual/i)).not.toBeInTheDocument();
  });

  it("renders an error message when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network error"))),
    );

    render(<Overview />);

    await waitFor(() => expect(screen.getByText(/couldn't reach the backend/i)).toBeInTheDocument());
  });

  it("lists resource groups derived from the inventory endpoint, with resource counts", async () => {
    mockFetchResponses({
      [COST_FRAGMENT]: EMPTY_COST,
      [FORECAST_FRAGMENT]: EMPTY_FORECAST,
      [INVENTORY_FRAGMENT]: { resources: [RG_A_VM, RG_A_DISK, RG_B_STORAGE] },
    });

    render(<Overview />);

    await waitFor(() => expect(screen.getByText("rg-a")).toBeInTheDocument());
    expect(screen.getByText("rg-b")).toBeInTheDocument();
    expect(screen.getByText("2 resources")).toBeInTheDocument();
    expect(screen.getByText("1 resource")).toBeInTheDocument();
  });

  it("drills from subscription -> resource group -> resource with working breadcrumb navigation, showing real scoped spend at every level", async () => {
    const user = userEvent.setup();
    const VM_COST = { series: [{ date: "2026-09-01", actual_cost: 42 }] };
    const VM_FORECAST = {
      insufficient_data: false,
      daily_rate: 42,
      horizon_days: 90,
      rollups: { "7": 294, "90": 3780 },
      series: [{ date: "2026-09-02", projected_cost: 42 }],
    };

    mockFetchResponses({
      // Aggregate/resource-group level stay "insufficient data"; the
      // resource-scoped request (resource_id=res-1) returns real data, so
      // the test can confirm SpendPanel is actually switching scope, not
      // just re-rendering the same response.
      [COST_FRAGMENT]: (url: string) => (url.includes("resource_id=res-1") ? VM_COST : EMPTY_COST),
      [FORECAST_FRAGMENT]: (url: string) => (url.includes("resource_id=res-1") ? VM_FORECAST : EMPTY_FORECAST),
      // The real /api/v1/inventory endpoint filters by resource_group server-side
      // (see backend/app/services/inventory_listing.py) - mirror that here so the
      // resource-group-level fetch only returns rg-a's own resources.
      [INVENTORY_FRAGMENT]: (url: string) =>
        url.includes("resource_group=rg-a") ? { resources: [RG_A_VM] } : { resources: [RG_A_VM, RG_B_STORAGE] },
    });

    render(<Overview />);

    await waitFor(() => expect(screen.getByText("rg-a")).toBeInTheDocument());
    await user.click(screen.getByText("rg-a"));

    // Resource-group level: breadcrumb shows the group, resource list is scoped to it.
    await waitFor(() => expect(screen.getByText(/resources in rg-a/i)).toBeInTheDocument());
    expect(screen.getByText("vm-web-01")).toBeInTheDocument();
    expect(screen.queryByText("stlogs01")).not.toBeInTheDocument();

    await user.click(screen.getByText("vm-web-01"));

    // Resource level: identity detail + a real spend figure/chart scoped to
    // just this resource (Task 16 closes the gap Task 15 flagged here).
    await waitFor(() => expect(screen.getByText("microsoft.compute/virtualmachines")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("$42.00")).toBeInTheDocument());
    expect(screen.getByText(/spend trend/i)).toBeInTheDocument();
    expect(screen.queryByText(/wired up yet/i)).not.toBeInTheDocument();

    // Breadcrumb back-navigation: rg-a -> Overview.
    await user.click(screen.getByRole("button", { name: "rg-a" }));
    await waitFor(() => expect(screen.getByText(/resources in rg-a/i)).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Overview" }));
    await waitFor(() => expect(screen.getByText("rg-a")).toBeInTheDocument());
    expect(screen.getByText("rg-b")).toBeInTheDocument();
  });

  it("shows a scoped empty state when a resource group has no cost history", async () => {
    const user = userEvent.setup();
    mockFetchResponses({
      [COST_FRAGMENT]: EMPTY_COST,
      [FORECAST_FRAGMENT]: EMPTY_FORECAST,
      [INVENTORY_FRAGMENT]: { resources: [RG_A_VM] },
    });

    render(<Overview />);

    await waitFor(() => expect(screen.getByText("rg-a")).toBeInTheDocument());
    await user.click(screen.getByText("rg-a"));

    await waitFor(() => expect(screen.getByText(/resource group "rg-a" hasn't synced/i)).toBeInTheDocument());
  });

  it("shows a scoped empty state when a resource has no cost history", async () => {
    const user = userEvent.setup();
    mockFetchResponses({
      [COST_FRAGMENT]: EMPTY_COST,
      [FORECAST_FRAGMENT]: EMPTY_FORECAST,
      [INVENTORY_FRAGMENT]: (url: string) =>
        url.includes("resource_group=rg-a") ? { resources: [RG_A_VM] } : { resources: [RG_A_VM] },
    });

    render(<Overview />);

    await waitFor(() => expect(screen.getByText("rg-a")).toBeInTheDocument());
    await user.click(screen.getByText("rg-a"));
    await waitFor(() => expect(screen.getByText("vm-web-01")).toBeInTheDocument());
    await user.click(screen.getByText("vm-web-01"));

    await waitFor(() => expect(screen.getByText(/vm-web-01 hasn't synced/i)).toBeInTheDocument());
  });
});
