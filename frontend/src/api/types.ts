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
