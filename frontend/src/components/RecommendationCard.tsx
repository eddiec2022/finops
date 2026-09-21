import type { RecommendationItem } from "../lib/normalizeRecommendations";
import { formatCurrency } from "../lib/formatCurrency";

export function RecommendationCard({ item }: { item: RecommendationItem }) {
  return (
    <div className="rounded-xl bg-brand-light p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-brand-dark">{item.title}</p>
          <p className="mt-1 text-sm text-brand-darker">{item.reason}</p>
        </div>
        <div className="shrink-0 text-right">
          {item.estimatedMonthlyImpact != null ? (
            <p className="font-mono text-lg font-semibold tabular-nums text-brand-dark">
              {formatCurrency(item.estimatedMonthlyImpact)}
              <span className="ml-1 text-xs font-normal text-brand-darker">/mo</span>
            </p>
          ) : (
            <p className="text-xs text-brand-darker">Savings not available</p>
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-brand-darker">{item.impactNote}</p>
    </div>
  );
}
