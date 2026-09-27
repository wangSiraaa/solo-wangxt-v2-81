import { ScenarioInput, SchemeInput, TimeSeriesInput } from '../models/api.model';

/**
 * 内置教学样例：7 个日时段。
 * 序列中包含：零来水（连续枯水，出现供水缺口并体现两种优先级差异）、
 * 超过库容上限的洪峰（弃水）、以及一处缺测（null，不补零，其后状态级联缺失）。
 */
export function buildSampleScenario(): ScenarioInput {
  const n = 7;
  const labels = ['第1天', '第2天', '第3天', '第4天', '第5天', '第6天', '第7天'];

  const inflow: TimeSeriesInput = {
    // 单位 m3/s：5、0、0（连续零来水，库容逼近死库容）、12、120（洪峰）、缺测、4
    values: [5, 0, 0, 12, 120, null, 4],
    unit: 'm3/s',
    kind: 'flow',
  };

  const evaporation: TimeSeriesInput = {
    values: [1.2, 1.3, 1.5, 1.6, 0.4, 1.1, 1.0],
    unit: 'mm',
    kind: 'evap',
    surface_area_m2: 1_000_000,
  };

  const environmentalFlow: TimeSeriesInput = {
    values: Array(n).fill(2), // 2 m3/s 生态基流
    unit: 'm3/s',
    kind: 'flow',
  };

  const schemeA: SchemeInput = {
    name: '方案A：城市优先',
    priority: 'urban_first',
    urban_demand: { values: [3, 3, 3, 3, 3, 3, 3], unit: 'm3/s', kind: 'flow' },
    agriculture_demand: { values: [4, 4, 4, 4, 4, 4, 4], unit: 'm3/s', kind: 'flow' },
  };

  const schemeB: SchemeInput = {
    name: '方案B：农业优先',
    priority: 'agriculture_first',
    urban_demand: { values: [3, 3, 3, 3, 3, 3, 3], unit: 'm3/s', kind: 'flow' },
    agriculture_demand: { values: [4, 4, 4, 4, 4, 4, 4], unit: 'm3/s', kind: 'flow' },
  };

  return {
    name: '教学样例：含零来水 / 缺水 / 洪峰 / 缺测的 7 日演算',
    timestep_hours: 24,
    labels,
    initial_storage_m3: 2_500_000,
    min_storage_m3: 1_000_000,
    max_storage_m3: 10_000_000,
    level_curve: [
      { storage_m3: 0, level_m: 80 },
      { storage_m3: 1_000_000, level_m: 90 },
      { storage_m3: 5_000_000, level_m: 105 },
      { storage_m3: 10_000_000, level_m: 115 },
    ],
    inflow,
    evaporation,
    environmental_flow: environmentalFlow,
    schemes: [schemeA, schemeB],
  };
}
