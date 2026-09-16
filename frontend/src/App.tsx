import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type HealthStatus = "checking" | "ok" | "unreachable";

function App() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((data) => setStatus(data.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center gap-4">
      <h1 className="text-3xl font-semibold">FinOps Platform — Phase 1</h1>
      <p className="text-slate-400">
        Backend health check:{" "}
        <span
          className={
            status === "ok"
              ? "text-emerald-400"
              : status === "unreachable"
                ? "text-red-400"
                : "text-slate-400"
          }
        >
          {status}
        </span>
      </p>
    </div>
  );
}

export default App;
