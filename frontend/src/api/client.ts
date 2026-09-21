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

/** Drill-down scope shared by the cost/forecast endpoints (inventory only uses resourceGroup). */
export interface DrillScope {
  resourceGroup?: string;
  resourceId?: string;
}

function scopeParams({ resourceGroup, resourceId }: DrillScope = {}, extra?: Record<string, string>): string {
  const params = new URLSearchParams(extra);
  if (resourceGroup) params.set("resource_group", resourceGroup);
  if (resourceId) params.set("resource_id", resourceId);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function getForecast(horizonDays: number, scope?: DrillScope): Promise<ForecastResponse> {
  return getJson(`/api/v1/forecast${scopeParams(scope, { horizon_days: String(horizonDays) })}`);
}

export function getCostHistory(scope?: DrillScope): Promise<CostHistoryResponse> {
  return getJson(`/api/v1/cost${scopeParams(scope)}`);
}

export function getResources(scope?: Pick<DrillScope, "resourceGroup">): Promise<InventoryResponse> {
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
