"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .engine.units import EvapUnit, FlowUnit, VolumeUnit


class PriorityMode(str, Enum):
    """两类用水（城市/市政、农业灌溉）之间的优先级。"""
    URBAN_FIRST = "urban_first"   # 城市优先，农业承担缺口
    AGRICULTURE_FIRST = "agriculture_first"  # 农业优先
    EQUAL = "equal"               # 同优先级，按需求比例分摊


# ---------- 输入 ----------

class CurvePoint(BaseModel):
    storage_m3: float = Field(..., ge=0, description="库容，立方米")
    level_m: float = Field(..., ge=0, description="水位，米")


class TimeSeriesInput(BaseModel):
    """一个时间序列。值用 None 表示缺测（不得补零）。"""
    values: list[float | None]
    unit: str = FlowUnit.CMS.value
    kind: Literal["flow", "volume", "evap"] = "flow"
    surface_area_m2: float | None = Field(None, description="蒸发为水深单位时使用")


class SchemeInput(BaseModel):
    """单个供水方案。"""
    name: str = "方案"
    priority: PriorityMode = PriorityMode.URBAN_FIRST
    # 允许两个用水户各自报"计划取水"；为 None 的时序列可省略，按 0 处理
    urban_demand: TimeSeriesInput | None = None
    agriculture_demand: TimeSeriesInput | None = None
    # 可选：本方案自己的生态基流/计划放水（缺省用场景级）
    environmental_flow: TimeSeriesInput | None = None


class ScenarioInput(BaseModel):
    """一次教学模拟场景。所有序列按固定时间步对齐。"""
    name: str = "未命名场景"
    timestep_hours: float = Field(24.0, gt=0)
    labels: list[str] = Field(default_factory=list, description="每个时段的标签，如日期")

    initial_storage_m3: float = Field(..., ge=0)
    min_storage_m3: float = Field(..., ge=0, description="死库容/下限（硬条件）")
    max_storage_m3: float = Field(..., gt=0, description="正常蓄水位对应库容/上限（硬条件）")

    level_curve: list[CurvePoint] = Field(..., min_length=2)

    inflow: TimeSeriesInput
    evaporation: TimeSeriesInput | None = None
    environmental_flow: TimeSeriesInput | None = Field(None, description="最低生态流量（硬条件）")

    schemes: list[SchemeInput] = Field(..., min_length=1, max_length=2)

    @model_validator(mode="after")
    def _check(self):
        n = len(self.inflow.values)
        if self.labels and len(self.labels) != n:
            raise ValueError("labels 长度必须与来水序列一致")
        if not (self.min_storage_m3 <= self.initial_storage_m3 <= self.max_storage_m3):
            raise ValueError("初始库容必须落在库容上下限之间")
        storages = sorted(p.storage_m3 for p in self.level_curve)
        if len(set(storages)) != len(storages):
            raise ValueError("库容曲线的库容值必须严格递增")
        if storages[0] > self.min_storage_m3 or storages[-1] < self.max_storage_m3:
            raise ValueError("库容曲线必须覆盖 [min_storage, max_storage] 区间")
        if self.evaporation and self.evaporation.unit in ("mm", "cm"):
            if not self.evaporation.surface_area_m2:
                raise ValueError("蒸发以水深给定时必须提供水面面积 surface_area_m2")
        for s in self.schemes:
            for ts in (s.urban_demand, s.agriculture_demand, s.environmental_flow):
                if ts is not None and len(ts.values) != n:
                    raise ValueError("所有时序列长度必须一致")
        for ts in (self.evaporation, self.environmental_flow):
            if ts is not None and len(ts.values) != n:
                raise ValueError("所有时序列长度必须一致")
        return self


# ---------- 输出 ----------

class PeriodResult(BaseModel):
    index: int
    label: str | None
    inflow_m3: float | None = Field(None, description="缺测时为 null，绝不写 0")
    evaporation_m3: float | None
    env_target_m3: float | None
    env_release_m3: float | None
    urban_demand_m3: float | None
    urban_supply_m3: float | None
    agriculture_demand_m3: float | None
    agriculture_supply_m3: float | None
    spill_m3: float | None
    storage_start_m3: float | None
    storage_end_m3: float | None
    level_end_m: float | None
    # 水量平衡校核：end - start - (in - evap - env - urban - agri - spill)
    balance_residual_m3: float | None
    shortage_m3: float | None
    feasible: bool = True
    missing_data: bool = False
    warnings: list[str] = Field(default_factory=list)


class SchemeSummary(BaseModel):
    name: str
    priority: PriorityMode
    total_inflow_m3: float | None
    total_evap_m3: float | None
    total_env_release_m3: float | None
    total_urban_supply_m3: float | None
    total_ag_supply_m3: float | None
    total_spill_m3: float | None
    total_demand_m3: float | None
    total_shortage_m3: float | None
    final_storage_m3: float | None
    max_level_m: float | None
    feasible_periods: int
    infeasible_periods: list[int] = Field(default_factory=list)
    missing_periods: list[int] = Field(default_factory=list)
    spill_periods: list[int] = Field(default_factory=list)


class SchemeResult(BaseModel):
    summary: SchemeSummary
    periods: list[PeriodResult]


class ConflictPeriod(BaseModel):
    index: int
    label: str | None
    reason: str
    required_m3: float | None
    available_m3: float | None


class SimulationResponse(BaseModel):
    scenario_id: int | None = None
    timestep_hours: float
    n_periods: int
    schemes: list[SchemeResult]
    conflicts: list[ConflictPeriod] = Field(
        default_factory=list,
        description="即使完全不供水也无法同时满足生态基流+死库容的时段",
    )
    disclaimer: str = "本系统为教学模拟，结果不替代现实供水调度决策。"


class ScenarioMeta(BaseModel):
    id: int
    name: str
    created_at: str
    payload: ScenarioInput
