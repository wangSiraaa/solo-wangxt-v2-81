// 与后端 schemas 对齐的类型定义

export type PriorityMode = 'urban_first' | 'agriculture_first' | 'equal';

export interface CurvePoint {
  storage_m3: number;
  level_m: number;
}

export interface TimeSeriesInput {
  values: (number | null)[];
  unit: string;
  kind: 'flow' | 'volume' | 'evap';
  surface_area_m2?: number | null;
}

export interface SchemeInput {
  name: string;
  priority: PriorityMode;
  urban_demand?: TimeSeriesInput | null;
  agriculture_demand?: TimeSeriesInput | null;
  environmental_flow?: TimeSeriesInput | null;
}

export interface ScenarioInput {
  name: string;
  timestep_hours: number;
  labels: string[];
  initial_storage_m3: number;
  min_storage_m3: number;
  max_storage_m3: number;
  level_curve: CurvePoint[];
  inflow: TimeSeriesInput;
  evaporation?: TimeSeriesInput | null;
  environmental_flow?: TimeSeriesInput | null;
  schemes: SchemeInput[];
}

export interface PeriodResult {
  index: number;
  label: string | null;
  inflow_m3: number | null;
  evaporation_m3: number | null;
  env_target_m3: number | null;
  env_release_m3: number | null;
  urban_demand_m3: number | null;
  urban_supply_m3: number | null;
  agriculture_demand_m3: number | null;
  agriculture_supply_m3: number | null;
  spill_m3: number | null;
  storage_start_m3: number | null;
  storage_end_m3: number | null;
  level_end_m: number | null;
  balance_residual_m3: number | null;
  shortage_m3: number | null;
  feasible: boolean;
  missing_data: boolean;
  warnings: string[];
}

export interface SchemeSummary {
  name: string;
  priority: PriorityMode;
  total_inflow_m3: number | null;
  total_evap_m3: number | null;
  total_env_release_m3: number | null;
  total_urban_supply_m3: number | null;
  total_ag_supply_m3: number | null;
  total_spill_m3: number | null;
  total_demand_m3: number | null;
  total_shortage_m3: number | null;
  final_storage_m3: number | null;
  max_level_m: number | null;
  feasible_periods: number;
  infeasible_periods: number[];
  missing_periods: number[];
  spill_periods: number[];
}

export interface SchemeResult {
  summary: SchemeSummary;
  periods: PeriodResult[];
}

export interface ConflictPeriod {
  index: number;
  label: string | null;
  reason: string;
  required_m3: number | null;
  available_m3: number | null;
}

export interface SimulationResponse {
  scenario_id: number | null;
  timestep_hours: number;
  n_periods: number;
  schemes: SchemeResult[];
  conflicts: ConflictPeriod[];
  disclaimer: string;
}

export interface ScenarioMeta {
  id: number;
  name: string;
  created_at: string;
  payload: ScenarioInput;
}
