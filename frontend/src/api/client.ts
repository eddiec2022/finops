import type { CostHistoryResponse, ForecastResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return response.json();
}

export function getForecast(horizonDays: number): Promise<ForecastResponse> {
  return getJson(`/api/v1/forecast?horizon_days=${horizonDays}`);
}

export function getCostHistory(): Promise<CostHistoryResponse> {
  return getJson("/api/v1/cost");
}
