import { useState } from "react";
import { Overview } from "./pages/Overview";
import { Recommendations } from "./pages/Recommendations";

type Page = "overview" | "recommendations";

const NAV_ITEMS: { key: Page; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "recommendations", label: "Recommendations" },
];

function App() {
  const [page, setPage] = useState<Page>("overview");

  return (
    <div className="min-h-screen bg-stone-50 text-stone-900">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <header className="mb-8">
          <p className="text-sm font-medium text-brand">FinOps Platform</p>
          <nav className="mt-2 flex gap-1">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setPage(item.key)}
                className={
                  "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors " +
                  (page === item.key ? "bg-brand text-white" : "text-stone-600 hover:bg-stone-100")
                }
              >
                {item.label}
              </button>
            ))}
          </nav>
        </header>

        {page === "overview" ? <Overview /> : <Recommendations />}
      </div>
    </div>
  );
}

export default App;
