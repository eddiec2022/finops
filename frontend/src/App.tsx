import { useEffect, useState } from "react";
import { getCostHistory, getForecast } from "./api/client";
import type { CostHistoryResponse, ForecastResponse } from "./api/types";
import { EmptyState } from "./components/EmptyState";
import { SpendChart } from "./components/SpendChart";
import { combineSpendSeries } from "./lib/combineSpendSeries";
import { formatCurrency } from "./lib/formatCurrency";

const FORECAST_HORIZON_DAYS = 90;
const TRAILING_SPEND_DAYS = 30;

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "empty" }
  | { status: "ready"; history: CostHistoryResponse; forecast: ForecastResponse };

function sumTrailingActual(history: CostHistoryResponse, days: number): number {
  return history.series.slice(-days).reduce((total, point) => total + point.actual_cost, 0);
}

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    Promise.all([getCostHistory(), getForecast(FORECAST_HORIZON_DAYS)])
      .then(([history, forecast]) => {
        // Both endpoints derive from the same underlying daily-cost query for
        // the unfiltered aggregate case, so forecast.insufficient_data alone
        // is a reliable signal that there's no history to show either.
        if (forecast.insufficient_data) {
          setState({ status: "empty" });
          return;
        }
        setState({ status: "ready", history, forecast });
      })
      .catch(() => setState({ status: "error" }));
  }, []);

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <header className="mb-8">
          <p className="text-sm font-medium text-brand">FinOps Platform</p>
          <h1 className="text-2xl font-semibold">Overview</h1>
        </header>

        {state.status === "loading" && <p className="text-stone-500">Loading spend data…</p>}

        {state.status === "error" && (
          <div className="rounded-xl bg-red-50 px-6 py-8 text-red-800">
            Couldn't reach the backend. Check that the API is running and try again.
          </div>
        )}

        {state.status === "empty" && <EmptyState />}

        {state.status === "ready" && (
          <div className="space-y-6">
            <div className="rounded-xl bg-white p-6 shadow-sm">
              <p className="text-sm text-stone-500">
                Spend, last {Math.min(TRAILING_SPEND_DAYS, state.history.series.length)} days
              </p>
              <p className="mt-1 font-mono text-4xl font-semibold tabular-nums text-brand-dark">
                {formatCurrency(sumTrailingActual(state.history, TRAILING_SPEND_DAYS))}
              </p>
            </div>

            <div className="rounded-xl bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-baseline justify-between">
                <h2 className="text-sm font-medium text-stone-700">
                  Spend trend &amp; {FORECAST_HORIZON_DAYS}-day forecast
                </h2>
                <span className="text-xs text-stone-400">Solid = actual · Dashed = projected</span>
              </div>
              <SpendChart data={combineSpendSeries(state.history.series, state.forecast.series)} />
              <p className="mt-3 text-xs text-stone-400">
                Projection is a simple linear burn-rate estimate based on recent daily spend — not a
                precise prediction.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
