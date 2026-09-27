"""API 请求/响应模型与输入校验，并负责把用户单位换算为引擎所需的 SI 单位。"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from . import units
from .engine import ReservoirCurve, SimConfig, TimeSeries


class Units(BaseModel):
    flow: str = "m3/s"          # 见 units.FLOW_TO_SI
    volume: str = "m3"          # 见 units.VOLUME_TO_SI
    evaporation: str = "mm/step"  # mm/step 或 mm/d


class CurveIn(BaseModel):
    storage: list[float] = Field(min_length=2)  # 库容，严格递增
    level: list[float] = Field(min_length=2)    # 水位
    area: list[float] = Field(min_length=2)     # 水面面积


class ScenarioIn(BaseModel):
    """一个供水模拟场景。数值单位由 units 字段声明，入库前换算为 SI。"""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    dt_seconds: float = Field(default=86400, gt=0)
    storage_min: float = Field(ge=0)
    storage_max: float = Field(gt=0)
    storage_initial: float = Field(ge=0)
    eco_flow: float = Field(ge=0, description="最小生态下泄流量（硬条件）")
    priority: list[str] = Field(min_length=2, max_length=2,
                                description="两类用水按优先级排列，前者优先")
    demands: dict[str, list[float]] = Field(min_length=2, max_length=2)
    inflow: list[float | None] = Field(min_length=1, description="入流序列，null 表示缺测")
    evaporation: list[float] = Field(min_length=1)
    curve: CurveIn
    units: Units = Units()

    @model_validator(mode="after")
    def check_consistency(self) -> "ScenarioIn":
        if self.storage_min >= self.storage_max:
            raise ValueError("库容下限必须小于上限")
        if not (self.storage_min <= self.storage_initial <= self.storage_max):
            raise ValueError("初始库容必须位于库容上下限之间")
        if len(self.demands) != 2:
            raise ValueError("本教学模型恰好支持两类用水")
        if sorted(self.priority) != sorted(self.demands.keys()):
            raise ValueError("priority 必须是两类用水名称的一个排列")
        n = len(self.inflow)
        if len(self.evaporation) != n:
            raise ValueError("蒸发序列长度必须与入流序列一致")
        for name, series in self.demands.items():
            if len(series) != n:
                raise ValueError(f"用水需求序列（{name}）长度必须与入流序列一致")
        for label, series in (("入流", self.inflow), ("蒸发", self.evaporation)):
            for v in series:
                if v is not None and v < 0:
                    raise ValueError(f"{label}不能为负")
        for name, series in self.demands.items():
            if any(v < 0 for v in series):
                raise ValueError(f"用水需求（{name}）不能为负")
        c = self.curve
        if not (len(c.storage) == len(c.level) == len(c.area)):
            raise ValueError("库容曲线的 storage/level/area 长度必须一致")
        if any(b <= a for a, b in zip(c.storage, c.storage[1:])):
            raise ValueError("库容曲线的库容值必须严格递增")
        return self

    def to_engine(self) -> tuple[SimConfig, TimeSeries, ReservoirCurve]:
        """按声明单位把场景换算为 SI，构造引擎输入。"""
        u = self.units
        vu = u.volume
        cfg = SimConfig(
            dt_seconds=self.dt_seconds,
            storage_min=units.volume_to_si(self.storage_min, vu),
            storage_max=units.volume_to_si(self.storage_max, vu),
            storage_initial=units.volume_to_si(self.storage_initial, vu),
            eco_flow=units.flow_to_si([self.eco_flow], u.flow)[0],
            priority=(self.priority[0], self.priority[1]),
        )
        ts = TimeSeries(
            inflow=units.flow_to_si(self.inflow, u.flow),
            evaporation=units.evap_to_si(self.evaporation, u.evaporation, self.dt_seconds),
            demands={
                k: [v if v is not None else 0.0 for v in units.flow_to_si(list(vs), u.flow)]
                for k, vs in self.demands.items()
            },
        )
        curve = ReservoirCurve(
            storage=[units.volume_to_si(v, vu) for v in self.curve.storage],
            level=list(self.curve.level),
            area=list(self.curve.area),
        )
        return cfg, ts, curve


class ScenarioOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: str | None = None


class CompareRequest(BaseModel):
    """两个方案对比：可传已保存场景 id，也可直接内联场景定义。"""

    a_id: int | None = None
    b_id: int | None = None
    a: ScenarioIn | None = None
    b: ScenarioIn | None = None

    @model_validator(mode="after")
    def check_sources(self) -> "CompareRequest":
        if self.a is None and self.a_id is None:
            raise ValueError("方案 A 必须给出 a_id 或内联 a")
        if self.b is None and self.b_id is None:
            raise ValueError("方案 B 必须给出 b_id 或内联 b")
        return self
