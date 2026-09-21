import type {
  CostHistoryResponse,
  ForecastResponse,
  IdleResourcesResponse,
  InventoryResponse,
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

/** Drill-down scope shared by the cost/forecast/inventory endpoints. */
export interface DrillScope {
  resourceGroup?: string;
}

function scopeParams({ resourceGroup }: DrillScope = {}): string {
  const params = new URLSearchParams();
  if (resourceGroup) params.set("resource_group", resourceGroup);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function getForecast(horizonDays: number, scope?: DrillScope): Promise<ForecastResponse> {
  const params = new URLSearchParams({ horizon_days: String(horizonDays) });
  if (scope?.resourceGroup) params.set("resource_group", scope.resourceGroup);
  return getJson(`/api/v1/forecast?${params.toString()}`);
}

export function getCostHistory(scope?: DrillScope): Promise<CostHistoryResponse> {
  return getJson(`/api/v1/cost${scopeParams(scope)}`);
}

export function getResources(scope?: DrillScope): Promise<InventoryResponse> {
  return getJson(`/api/v1/inventory${scopeParams(scope)}`);
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
