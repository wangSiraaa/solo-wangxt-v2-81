/** 与后端 API 对应的数据结构 */

export interface Units {
  flow: string;         // m3/s | L/s | m3/h | 万m3/d
  volume: string;       // m3 | 万m3 | 百万m3
  evaporation: string;  // mm/step | mm/d
}

export interface CurveIn {
  storage: number[];
  level: number[];
  area: number[];
}

export interface ScenarioIn {
  name: string;
  description: string;
  dt_seconds: number;
  storage_min: number;
  storage_max: number;
  storage_initial: number;
  eco_flow: number;
  priority: string[];
  demands: { [use: string]: number[] };
  inflow: (number | null)[];
  evaporation: number[];
  curve: CurveIn;
  units: Units;
}

export interface ConflictStep {
  step: number;
  code: string;
  message: string;
}

export interface SimSummary {
  total_inflow_volume: number;
  total_evaporation_volume: number;
  total_eco_release_volume: number;
  total_withdrawal_volume: { [use: string]: number };
  total_deficit_volume: { [use: string]: number };
  total_spill_volume: number;
  missing_steps: number[];
  conflict_steps: ConflictStep[];
  max_abs_balance_error: number;
  min_storage: number | null;
  max_storage: number | null;
}

export interface SimResult {
  n_steps: number;
  dt_seconds: number;
  storage_min: number;
  storage_max: number;
  storage_initial: number;
  eco_flow: number;
  priority: string[];
  demands: { [use: string]: number[] };
  inflow: (number | null)[];
  storage: (number | null)[];
  level: (number | null)[];
  evaporation_volume: (number | null)[];
  eco_release: (number | null)[];
  withdrawals: { [use: string]: (number | null)[] };
  deficits: { [use: string]: (number | null)[] };
  spill: (number | null)[];
  missing_inflow: boolean[];
  estimated_start: boolean[];
  conflicts: (string | null)[];
  balance_error: (number | null)[];
  summary: SimSummary;
}

export interface ScenarioMeta {
  id: number;
  name: string;
  description: string;
  created_at?: string;
}

export interface CompareResponse {
  a: { name: string; result: SimResult };
  b: { name: string; result: SimResult };
  diff: {
    total_deficit_volume: { [use: string]: number };
    total_spill_volume: number;
    total_eco_release_volume: number;
    n_conflict_steps: { a: number; b: number };
    min_storage: { a: number | null; b: number | null };
  };
}
