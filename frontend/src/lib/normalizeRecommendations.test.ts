import { describe, expect, it } from "vitest";
import {
  normalizeIdleResources,
  normalizeNonPeakScheduling,
  normalizeReservedInstances,
  normalizeRightsizing,
} from "./normalizeRecommendations";

describe("normalizeRightsizing", () => {
  it("builds a reason from the suggested SKU and CPU evidence", () => {
    const [item] = normalizeRightsizing({
      idle_cpu_threshold_percent: 10,
      idle_lookback_days: 14,
      recommendations: [
        {
          provider: "azure",
          resource_id: "r1",
          external_resource_id: "/subscriptions/.../vm-1",
          resource_type: "microsoft.compute/virtualmachines",
          resource_group: "rg-a",
          region: "eastus",
          current_sku: "Standard_D4s_v3",
          suggested_sku: "Standard_D2s_v3",
          suggestion_note: "Halved core count within the same series.",
          avg_cpu_percent: 3.2,
          lookback_days: 14,
          estimated_monthly_savings: 45.5,
          savings_note: "Approximate, not a billing quote.",
        },
      ],
    });

    expect(item.title).toBe("vm-1");
    expect(item.reason).toBe("Standard_D4s_v3 → Standard_D2s_v3 (avg CPU 3.2% over 14d)");
    expect(item.estimatedMonthlyImpact).toBe(45.5);
  });

  it("falls back to the suggestion note when there's no specific suggested SKU", () => {
    const [item] = normalizeRightsizing({
      idle_cpu_threshold_percent: 10,
      idle_lookback_days: 14,
      recommendations: [
        {
          provider: "azure",
          resource_id: "r2",
          external_resource_id: null,
          resource_type: "microsoft.web/sites",
          resource_group: null,
          region: null,
          current_sku: "P1v2",
          suggested_sku: null,
          suggestion_note: "Already the smallest tier - no specific suggestion.",
          avg_cpu_percent: 1.0,
          lookback_days: 14,
          estimated_monthly_savings: null,
          savings_note: "No specific suggested size to compare against; savings can't be estimated.",
        },
      ],
    });

    expect(item.title).toBe("r2");
    expect(item.reason).toBe("Idle at 1% avg CPU over 14d - Already the smallest tier - no specific suggestion.");
    expect(item.estimatedMonthlyImpact).toBeNull();
  });
});

describe("normalizeIdleResources", () => {
  it("turns the reason slug and detail into a readable sentence", () => {
    const [item] = normalizeIdleResources({
      idle_lookback_days: 14,
      recommendations: [
        {
          provider: "azure",
          resource_id: "r3",
          external_resource_id: "/subscriptions/.../disk-1",
          resource_type: "microsoft.compute/disks",
          resource_group: "rg-a",
          region: "eastus",
          reason: "unattached_disk",
          detail: "diskState is Unattached",
          estimated_monthly_waste: 12.0,
          waste_note: "Approximate, not a billing quote.",
        },
      ],
    });

    expect(item.reason).toBe("unattached disk - diskState is Unattached");
    expect(item.estimatedMonthlyImpact).toBe(12.0);
  });
});

describe("normalizeNonPeakScheduling", () => {
  it("joins every matched signal's detail into the reason", () => {
    const [item] = normalizeNonPeakScheduling({
      idle_lookback_days: 14,
      off_peak_usage_ratio_threshold: 0.5,
      business_hours_definition: "Fixed weekday 09:00-17:00 UTC window.",
      recommendations: [
        {
          provider: "azure",
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
    });

    expect(item.reason).toBe("resource name contains 'dev'");
    expect(item.estimatedMonthlyImpact).toBe(6.93);
  });
});

describe("normalizeReservedInstances", () => {
  it("builds a title from SKU + location and a reason from quantity/term/scope", () => {
    const [item] = normalizeReservedInstances({
      source: "Azure Microsoft.Consumption reservationRecommendations API",
      field_mapping_note: "Unverified against real populated data.",
      recommendations: [
        {
          provider: "azure",
          id: "/subscriptions/.../reservationRecommendations/abc123",
          sku: "Standard_D2s_v3",
          location: "eastus",
          resource_type: "VirtualMachines",
          scope: "Single",
          term: "P1Y",
          look_back_period: "Last30Days",
          recommended_quantity: 2,
          cost_with_no_reserved_instances: 500,
          total_cost_with_reserved_instances: 320,
          estimated_monthly_savings: 180,
          currency: "USD",
        },
      ],
    });

    expect(item.title).toBe("Standard_D2s_v3 · eastus");
    expect(item.reason).toBe("Reserve 2 instance(s), P1Y term, Single scope");
    expect(item.estimatedMonthlyImpact).toBe(180);
    expect(item.impactNote).toBe("Unverified against real populated data.");
  });

  it("falls back to a generated id and generic title when the API item has none", () => {
    const [item] = normalizeReservedInstances({
      source: "Azure Microsoft.Consumption reservationRecommendations API",
      field_mapping_note: "Unverified against real populated data.",
      recommendations: [
        {
          provider: "azure",
          id: null,
          sku: null,
          location: null,
          resource_type: null,
          scope: null,
          term: null,
          look_back_period: null,
          recommended_quantity: null,
          cost_with_no_reserved_instances: null,
          total_cost_with_reserved_instances: null,
          estimated_monthly_savings: null,
          currency: null,
        },
      ],
    });

    expect(item.id).toBe("reserved-instance-0");
    expect(item.title).toBe("Reservation recommendation");
    expect(item.reason).toBe("");
  });

  it("builds a title/reason for an AWS reserved-instance item, a genuinely different shape than Azure's", () => {
    const [item] = normalizeReservedInstances({
      source: "AWS Cost Explorer APIs",
      field_mapping_note: "Not verified against real populated data.",
      recommendations: [
        {
          provider: "aws",
          recommendation_type: "reserved_instance",
          instance_type: "m5.large",
          location: "us-east-1",
          recommended_quantity: "2",
          term: "ONE_YEAR",
          estimated_monthly_savings: "30.00",
        },
      ],
    });

    expect(item.title).toBe("m5.large · us-east-1");
    expect(item.reason).toBe("Reserve 2 instance(s), ONE_YEAR term");
    expect(item.estimatedMonthlyImpact).toBe(30);
  });

  it("builds a title/reason for an AWS savings-plan item", () => {
    const [item] = normalizeReservedInstances({
      source: "AWS Cost Explorer APIs",
      field_mapping_note: "Not verified against real populated data.",
      recommendations: [
        {
          provider: "aws",
          recommendation_type: "savings_plan",
          instance_family: "m5",
          location: "us-east-1",
          hourly_commitment: "0.05",
          term: "ONE_YEAR",
          estimated_monthly_savings: "18.00",
        },
      ],
    });

    expect(item.title).toBe("m5 · us-east-1");
    expect(item.reason).toBe("$0.05/hr commitment, ONE_YEAR term");
    expect(item.estimatedMonthlyImpact).toBe(18);
  });
});
