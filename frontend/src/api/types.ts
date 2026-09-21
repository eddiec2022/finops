export interface ForecastPoint {
  date: string;
  projected_cost: number;
}

export interface ForecastResponse {
  insufficient_data: boolean;
  daily_rate: number | null;
  horizon_days: number;
  rollups: Record<string, number>;
  series: ForecastPoint[];
}

export interface CostHistoryPoint {
  date: string;
  actual_cost: number;
}

export interface CostHistoryResponse {
  series: CostHistoryPoint[];
}

export interface ResourceListItem {
  resource_id: string;
  external_resource_id: string | null;
  name: string | null;
  /** "azure" | "aws" | "gcp" - lets the UI adapt copy (e.g. drill-down labels) without hardcoding a provider. */
  provider: string;
  resource_group: string | null;
  resource_type: string;
  region: string | null;
}

export interface InventoryResponse {
  resources: ResourceListItem[];
}

export interface RightsizingRecommendation {
  resource_id: string;
  external_resource_id: string | null;
  resource_type: string;
  resource_group: string | null;
  region: string | null;
  current_sku: string | null;
  suggested_sku: string | null;
  suggestion_note: string;
  avg_cpu_percent: number;
  lookback_days: number;
  estimated_monthly_savings: number | null;
  savings_note: string;
}

export interface RightsizingResponse {
  idle_cpu_threshold_percent: number;
  idle_lookback_days: number;
  recommendations: RightsizingRecommendation[];
}

export interface IdleResourceRecommendation {
  resource_id: string;
  external_resource_id: string | null;
  resource_type: string;
  resource_group: string | null;
  region: string | null;
  reason: string;
  detail: string;
  estimated_monthly_waste: number | null;
  waste_note: string;
}

export interface IdleResourcesResponse {
  idle_lookback_days: number;
  recommendations: IdleResourceRecommendation[];
}

export interface NonPeakSignal {
  matched: boolean;
  detail: string;
}

export interface NonPeakUsageSignal extends NonPeakSignal {
  peak_avg_cpu_percent: number | null;
  off_peak_avg_cpu_percent: number | null;
}

export interface NonPeakSchedulingRecommendation {
  resource_id: string;
  external_resource_id: string | null;
  resource_type: string;
  resource_group: string | null;
  region: string | null;
  signals: {
    tag: NonPeakSignal;
    naming: NonPeakSignal;
    usage_pattern: NonPeakUsageSignal;
  };
  recommended_schedule: string;
  estimated_monthly_savings: number | null;
  savings_note: string;
}

export interface NonPeakSchedulingResponse {
  idle_lookback_days: number;
  off_peak_usage_ratio_threshold: number;
  business_hours_definition: string;
  recommendations: NonPeakSchedulingRecommendation[];
}

export interface ReservedInstanceRecommendation {
  id: string | null;
  sku: string | null;
  location: string | null;
  resource_type: string | null;
  scope: string | null;
  term: string | null;
  look_back_period: string | null;
  recommended_quantity: number | null;
  cost_with_no_reserved_instances: number | null;
  total_cost_with_reserved_instances: number | null;
  estimated_monthly_savings: number | null;
  currency: string | null;
}

export interface ReservedInstancesResponse {
  source: string;
  field_mapping_note: string;
  recommendations: ReservedInstanceRecommendation[];
}
