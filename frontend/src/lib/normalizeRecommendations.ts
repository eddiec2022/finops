import type {
  IdleResourcesResponse,
  NonPeakSchedulingRecommendation,
  NonPeakSchedulingResponse,
  ReservedInstanceRecommendation,
  ReservedInstancesResponse,
  RightsizingResponse,
} from "../api/types";

export type RecommendationCategory =
  | "rightsizing"
  | "idle-resources"
  | "non-peak-scheduling"
  | "reserved-instances";

export const CATEGORY_LABELS: Record<RecommendationCategory, string> = {
  rightsizing: "Rightsizing",
  "idle-resources": "Idle & Orphaned Resources",
  "non-peak-scheduling": "Non-Peak Scheduling",
  "reserved-instances": "Reserved Instances / Savings Plans",
};

export interface RecommendationItem {
  id: string;
  category: RecommendationCategory;
  title: string;
  reason: string;
  estimatedMonthlyImpact: number | null;
  impactNote: string;
}

// ARM resource IDs (e.g. /subscriptions/.../resourceGroups/rg/providers/.../vm-1)
// are unique but not remotely readable as a title - the resource's own name is
// always the last path segment.
function resourceDisplayName(externalResourceId: string | null, fallbackId: string): string {
  if (!externalResourceId) return fallbackId;
  const segments = externalResourceId.split("/").filter(Boolean);
  return segments[segments.length - 1] || fallbackId;
}

export function normalizeRightsizing(response: RightsizingResponse): RecommendationItem[] {
  return response.recommendations.map((r) => ({
    id: r.resource_id,
    category: "rightsizing",
    title: resourceDisplayName(r.external_resource_id, r.resource_id),
    reason: r.suggested_sku
      ? `${r.current_sku ?? "current SKU"} → ${r.suggested_sku} (avg CPU ${r.avg_cpu_percent}% over ${r.lookback_days}d)`
      : `Idle at ${r.avg_cpu_percent}% avg CPU over ${r.lookback_days}d - ${r.suggestion_note}`,
    estimatedMonthlyImpact: r.estimated_monthly_savings,
    impactNote: r.savings_note,
  }));
}

export function normalizeIdleResources(response: IdleResourcesResponse): RecommendationItem[] {
  return response.recommendations.map((r) => ({
    id: r.resource_id,
    category: "idle-resources",
    title: resourceDisplayName(r.external_resource_id, r.resource_id),
    reason: `${r.reason.replace(/_/g, " ")} - ${r.detail}`,
    estimatedMonthlyImpact: r.estimated_monthly_waste,
    impactNote: r.waste_note,
  }));
}

function matchedSignalSummary(signals: NonPeakSchedulingRecommendation["signals"]): string {
  const matched = [
    signals.tag.matched ? signals.tag.detail : null,
    signals.naming.matched ? signals.naming.detail : null,
    signals.usage_pattern.matched ? signals.usage_pattern.detail : null,
  ].filter((detail): detail is string => detail !== null);

  // The backend only includes a resource here when at least one signal
  // matched (tag OR name OR usage pattern), so this fallback shouldn't be
  // reachable in practice - kept as a safe default rather than assuming.
  return matched.length > 0 ? matched.join("; ") : "flagged by a non-peak-scheduling signal";
}

export function normalizeNonPeakScheduling(response: NonPeakSchedulingResponse): RecommendationItem[] {
  return response.recommendations.map((r) => ({
    id: r.resource_id,
    category: "non-peak-scheduling",
    title: resourceDisplayName(r.external_resource_id, r.resource_id),
    reason: matchedSignalSummary(r.signals),
    estimatedMonthlyImpact: r.estimated_monthly_savings,
    impactNote: r.savings_note,
  }));
}

// AWS's two recommendation kinds (Reserved Instances, Savings Plans) use
// different field names than Azure's single API, not just different values -
// see the ReservedInstanceRecommendation type's own comment. Branches on
// `provider`/`recommendation_type` rather than assuming one shape fits both.
function normalizeReservedInstanceItem(r: ReservedInstanceRecommendation, index: number): RecommendationItem {
  const savings = r.estimated_monthly_savings;
  const estimatedMonthlyImpact = typeof savings === "string" ? Number(savings) : savings ?? null;

  if (r.provider === "aws") {
    const isSavingsPlan = r.recommendation_type === "savings_plan";
    const title = isSavingsPlan
      ? [r.instance_family, r.location].filter(Boolean).join(" · ") || "Savings Plan recommendation"
      : [r.instance_type, r.location].filter(Boolean).join(" · ") || "Reserved Instance recommendation";
    const reason = isSavingsPlan
      ? [r.hourly_commitment ? `$${r.hourly_commitment}/hr commitment` : null, r.term ? `${r.term} term` : null]
          .filter((part): part is string => part !== null)
          .join(", ")
      : [
          r.recommended_quantity != null ? `Reserve ${r.recommended_quantity} instance(s)` : null,
          r.term ? `${r.term} term` : null,
        ]
          .filter((part): part is string => part !== null)
          .join(", ");
    return {
      id: `${r.recommendation_type ?? "aws-reservation"}-${index}`,
      category: "reserved-instances",
      title,
      reason,
      estimatedMonthlyImpact: Number.isFinite(estimatedMonthlyImpact) ? (estimatedMonthlyImpact as number) : null,
      impactNote: "",
    };
  }

  return {
    id: r.id ?? `reserved-instance-${index}`,
    category: "reserved-instances",
    title: [r.sku, r.location].filter(Boolean).join(" · ") || "Reservation recommendation",
    reason: [
      r.recommended_quantity != null ? `Reserve ${r.recommended_quantity} instance(s)` : null,
      r.term ? `${r.term} term` : null,
      r.scope ? `${r.scope} scope` : null,
    ]
      .filter((part): part is string => part !== null)
      .join(", "),
    estimatedMonthlyImpact: Number.isFinite(estimatedMonthlyImpact) ? (estimatedMonthlyImpact as number) : null,
    impactNote: "",
  };
}

// field_mapping_note is a plain string when only one provider contributed
// recommendations (the pre-existing shape), or {azure, aws} once both did
// (Task 21) - each item gets its own provider's note in the merged case,
// rather than one note (or a stringified object) applied to every item
// regardless of which provider it actually came from.
function impactNoteFor(r: ReservedInstanceRecommendation, note: ReservedInstancesResponse["field_mapping_note"]): string {
  if (typeof note === "string") return note;
  return r.provider === "aws" ? note.aws : note.azure;
}

export function normalizeReservedInstances(response: ReservedInstancesResponse): RecommendationItem[] {
  return response.recommendations.map((r, index) => ({
    ...normalizeReservedInstanceItem(r, index),
    impactNote: impactNoteFor(r, response.field_mapping_note),
  }));
}
