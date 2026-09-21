import { useEffect, useState } from "react";
import {
  getIdleResourceRecommendations,
  getNonPeakSchedulingRecommendations,
  getReservedInstanceRecommendations,
  getRightsizingRecommendations,
} from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { RecommendationCard } from "../components/RecommendationCard";
import {
  CATEGORY_LABELS,
  normalizeIdleResources,
  normalizeNonPeakScheduling,
  normalizeReservedInstances,
  normalizeRightsizing,
  type RecommendationCategory,
  type RecommendationItem,
} from "../lib/normalizeRecommendations";

type CategoryState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; items: RecommendationItem[] };

const CATEGORY_ORDER: RecommendationCategory[] = [
  "rightsizing",
  "idle-resources",
  "non-peak-scheduling",
  "reserved-instances",
];

function sortByImpactDesc(items: RecommendationItem[]): RecommendationItem[] {
  return [...items].sort(
    (a, b) => (b.estimatedMonthlyImpact ?? -Infinity) - (a.estimatedMonthlyImpact ?? -Infinity),
  );
}

export function Recommendations() {
  const [byCategory, setByCategory] = useState<Record<RecommendationCategory, CategoryState>>({
    rightsizing: { status: "loading" },
    "idle-resources": { status: "loading" },
    "non-peak-scheduling": { status: "loading" },
    "reserved-instances": { status: "loading" },
  });

  useEffect(() => {
    // Each category is fetched and its state updated independently (own
    // .then/.catch, not Promise.all) so one endpoint erroring degrades only
    // that section instead of blanking the whole page, per the task's
    // explicit requirement.
    const setCategory = (category: RecommendationCategory, state: CategoryState) =>
      setByCategory((prev) => ({ ...prev, [category]: state }));

    getRightsizingRecommendations()
      .then((response) => setCategory("rightsizing", { status: "ready", items: normalizeRightsizing(response) }))
      .catch(() => setCategory("rightsizing", { status: "error" }));

    getIdleResourceRecommendations()
      .then((response) =>
        setCategory("idle-resources", { status: "ready", items: normalizeIdleResources(response) }),
      )
      .catch(() => setCategory("idle-resources", { status: "error" }));

    getNonPeakSchedulingRecommendations()
      .then((response) =>
        setCategory("non-peak-scheduling", { status: "ready", items: normalizeNonPeakScheduling(response) }),
      )
      .catch(() => setCategory("non-peak-scheduling", { status: "error" }));

    getReservedInstanceRecommendations()
      .then((response) =>
        setCategory("reserved-instances", { status: "ready", items: normalizeReservedInstances(response) }),
      )
      .catch(() => setCategory("reserved-instances", { status: "error" }));
  }, []);

  const states = CATEGORY_ORDER.map((category) => byCategory[category]);
  const allSettled = states.every((state) => state.status !== "loading");
  const allReadyAndEmpty = states.every((state) => state.status === "ready" && state.items.length === 0);

  return (
    <div>
      <h1 className="mb-8 text-2xl font-semibold">Recommendations</h1>

      {!allSettled && <p className="text-stone-500">Loading recommendations…</p>}

      {allSettled && allReadyAndEmpty && (
        <EmptyState
          title="Nothing to flag right now"
          description="None of the four recommendation categories found anything to flag against this subscription's current usage and cost data. Check back as more usage history syncs in."
        />
      )}

      {allSettled && !allReadyAndEmpty && (
        <div className="space-y-8">
          {CATEGORY_ORDER.map((category) => {
            const state = byCategory[category];
            return (
              <section key={category}>
                <h2 className="mb-3 text-sm font-medium text-stone-700">{CATEGORY_LABELS[category]}</h2>

                {state.status === "error" && (
                  <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">
                    Couldn't load recommendations for this category. Try refreshing.
                  </div>
                )}

                {state.status === "ready" && state.items.length === 0 && (
                  <p className="text-sm text-stone-400">No recommendations in this category right now.</p>
                )}

                {state.status === "ready" && state.items.length > 0 && (
                  <div className="space-y-3">
                    {sortByImpactDesc(state.items).map((item) => (
                      <RecommendationCard key={item.id} item={item} />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
