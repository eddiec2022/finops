import type {
  CostHistoryResponse,
  ForecastResponse,
  IdleResourcesResponse,
  NonPeakSchedulingResponse,
  ReservedInstancesResponse,
  RightsizingResponse,
} from "./types";

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

export function getRightsizingRecommendations(): Promise<RightsizingResponse> {
  return getJson("/api/v1/recommendations/rightsizing");
}

export function getIdleResourceRecommendations(): Promise<IdleResourcesResponse> {
  return getJson("/api/v1/recommendations/idle-resources");
}

export function getNonPeakSchedulingRecommendations(): Promise<NonPeakSchedulingResponse> {
  return getJson("/api/v1/recommendations/non-peak-scheduling");
}

export function getReservedInstanceRecommendations(): Promise<ReservedInstancesResponse> {
  return getJson("/api/v1/recommendations/reserved-instances");
}
