"""构造测试用场景与引擎输入的公共工具。"""
from __future__ import annotations

from app.engine import ReservoirCurve, SimConfig, TimeSeries

# 简单教学库容曲线：0 → 1000 万 m³ 线性，水位 100→120 m，面积 0→200 万 m²
CURVE = ReservoirCurve(
    storage=[0.0, 5e6, 1e7],
    level=[100.0, 110.0, 120.0],
    area=[0.0, 1e6, 2e6],
)

DT = 86400.0  # 日步长


def make_config(**kw) -> SimConfig:
    defaults = dict(
        dt_seconds=DT,
        storage_min=1e6,
        storage_max=9e6,
        storage_initial=5e6,
        eco_flow=0.0,
        priority=("municipal", "agriculture"),
    )
    defaults.update(kw)
    return SimConfig(**defaults)


def make_series(n: int, inflow=0.0, evap=0.0, dem_m=0.0, dem_a=0.0) -> TimeSeries:
    """n 步序列；标量参数广播为常数序列。"""
    def broadcast(v):
        return list(v) if isinstance(v, (list, tuple)) else [v] * n

    return TimeSeries(
        inflow=broadcast(inflow),
        evaporation=broadcast(evap),
        demands={"municipal": broadcast(dem_m), "agriculture": broadcast(dem_a)},
    )


def scenario_payload(**over) -> dict:
    """一份合法的 API 场景 JSON（SI 单位），可按需覆盖字段。"""
    p = {
        "name": "测试场景",
        "description": "",
        "dt_seconds": 86400,
        "storage_min": 1e6,
        "storage_max": 9e6,
        "storage_initial": 5e6,
        "eco_flow": 0.0,
        "priority": ["municipal", "agriculture"],
        "demands": {"municipal": [0.0] * 4, "agriculture": [0.0] * 4},
        "inflow": [0.0] * 4,
        "evaporation": [0.0] * 4,
        "curve": {"storage": [0.0, 5e6, 1e7],
                  "level": [100.0, 110.0, 120.0],
                  "area": [0.0, 1e6, 2e6]},
        "units": {"flow": "m3/s", "volume": "m3", "evaporation": "mm/step"},
    }
    p.update(over)
    return p
