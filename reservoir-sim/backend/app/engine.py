"""水库水量平衡模拟引擎（教学用途）。

按固定时间步逐步计算：入流 → 蒸发 → 放水（生态流量 + 两类取水）→ 弃水 → 库容。
每一步严格满足水量守恒：

    S(t+1) = S(t) + I·Δt - E(t) - R·Δt - Spill·Δt

硬条件：
  * 库容下限 S_min / 上限 S_max —— 通过调节放水与弃水尽力维持；
  * 最小生态流量 —— 优先于一切取水分配。
当硬条件之间发生冲突（例如来水不足以同时满足生态流量和库容下限）时，
该时段被标记为冲突时段，并在结果中明确指出，绝不静默伪造可行解。

缺测来水：该时段所有结果记为缺失（None），而不是当作 0。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import interp1d

# 冲突类型编码（前端据此高亮）
CONFLICT_ECO_UNMET = "eco_flow_unmet"        # 可分配水量不足最小生态流量
CONFLICT_BELOW_MIN = "storage_below_min"     # 即使完全不放水，库容仍跌破下限（蒸发等不可控因素）

CONFLICT_MESSAGES = {
    CONFLICT_ECO_UNMET: "来水不足：无法满足最小生态流量（已优先保库容下限）",
    CONFLICT_BELOW_MIN: "蒸发损失过大：即使停止一切放水，库容仍跌破下限",
}


@dataclass
class ReservoirCurve:
    """库容曲线：库容(m³) → 水位(m) / 水面面积(m²)，线性插值。"""

    storage: np.ndarray  # 严格递增，m³
    level: np.ndarray    # m
    area: np.ndarray     # m²

    def __post_init__(self) -> None:
        s = np.asarray(self.storage, dtype=float)
        if s.ndim != 1 or len(s) < 2:
            raise ValueError("库容曲线至少需要两个点")
        if np.any(np.diff(s) <= 0):
            raise ValueError("库容曲线的库容值必须严格递增")
        self.storage = s
        self.level = np.asarray(self.level, dtype=float)
        self.area = np.asarray(self.area, dtype=float)
        if not (len(self.level) == len(self.area) == len(s)):
            raise ValueError("库容曲线的 storage/level/area 长度必须一致")
        self._level_of = interp1d(s, self.level, kind="linear", fill_value="extrapolate")
        self._area_of = interp1d(s, self.area, kind="linear", fill_value="extrapolate")

    def level_of(self, storage: float) -> float:
        """按库容曲线把库容换算为水位。"""
        return float(self._level_of(storage))

    def area_of(self, storage: float) -> float:
        """按库容曲线把库容换算为水面面积（不为负）。"""
        return max(0.0, float(self._area_of(storage)))


@dataclass
class SimConfig:
    dt_seconds: float          # 固定时间步长 Δt（秒）
    storage_min: float         # 库容下限（硬条件），m³
    storage_max: float         # 库容上限（硬条件），m³
    storage_initial: float     # 初始库容，m³
    eco_flow: float            # 最小生态下泄流量（硬条件），m³/s
    priority: tuple[str, str]  # 两类用水的优先级，前者优先


@dataclass
class TimeSeries:
    """已换算为 SI 单位的输入时间序列。"""

    inflow: list[float | None]      # 入流 m³/s；None 表示缺测
    evaporation: list[float]        # 蒸发水深 m/步
    demands: dict[str, list[float]] # 两类用水需求 m³/s

    @property
    def n_steps(self) -> int:
        return len(self.inflow)


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def simulate(cfg: SimConfig, ts: TimeSeries, curve: ReservoirCurve) -> dict:
    """逐时段执行水量平衡模拟，返回列式结果（便于前端绘图与表格展示）。"""
    n = ts.n_steps
    dt = cfg.dt_seconds
    use_names = list(cfg.priority)

    out: dict = {
        "n_steps": n,
        "dt_seconds": dt,
        # 回显关键配置（SI 单位），便于前端绘制库容上下限等参考线
        "storage_min": cfg.storage_min,
        "storage_max": cfg.storage_max,
        "storage_initial": cfg.storage_initial,
        "eco_flow": cfg.eco_flow,
        "priority": list(cfg.priority),
        "demands": ts.demands,                 # 需求 m³/s（SI，便于前端对照）
        "inflow": [None] * n,                  # m³/s（缺测为 None）
        "storage": [None] * n,                 # 时段末库容 m³
        "level": [None] * n,                   # 时段末水位 m（按库容曲线换算）
        "evaporation_volume": [None] * n,      # m³
        "eco_release": [None] * n,             # 实际生态下泄 m³/s
        "withdrawals": {k: [None] * n for k in use_names},  # 实际取水 m³/s
        "deficits": {k: [None] * n for k in use_names},     # 需求缺口 m³/s
        "spill": [None] * n,                   # 弃水 m³/s
        "missing_inflow": [False] * n,
        "estimated_start": [False] * n,        # 起始库容沿用了上一已知值
        "conflicts": [None] * n,               # 冲突类型编码或 None
        "balance_error": [None] * n,           # 每步水量守恒残差 m³（应≈0）
    }

    storage = cfg.storage_initial
    for t in range(n):
        inflow = ts.inflow[t]
        if _is_missing(inflow):
            # 缺测来水：本时段结果全部记为缺失，绝不按 0 处理。
            out["missing_inflow"][t] = True
            continue
        if t > 0 and out["storage"][t - 1] is None:
            out["estimated_start"][t] = True

        inflow = float(inflow)
        in_vol = inflow * dt
        evap_vol = ts.evaporation[t] * curve.area_of(storage)

        # 本时段在守住库容下限的前提下，可用于"生态流量 + 取水"的水量
        available = storage - cfg.storage_min + in_vol - evap_vol
        eco_need = cfg.eco_flow * dt

        conflict = None
        take_vol: dict[str, float] = {k: 0.0 for k in use_names}
        if available < 0.0:
            # 蒸发等不可控损失已使库容必然跌破下限
            eco_vol = 0.0
            conflict = CONFLICT_BELOW_MIN
        elif available < eco_need:
            # 硬条件冲突：生态流量与库容下限不可兼得，保下限并记录冲突时段
            eco_vol = max(available, 0.0)
            conflict = CONFLICT_ECO_UNMET
        else:
            eco_vol = eco_need
            remaining = available - eco_need
            for name in cfg.priority:  # 按优先级先后分配
                want = ts.demands[name][t] * dt
                take = min(want, max(remaining, 0.0))
                take_vol[name] = take
                remaining -= take

        release_vol = eco_vol + sum(take_vol.values())
        new_storage = storage + in_vol - evap_vol - release_vol

        # 库容上限：超出部分作为弃水（教学模型，不模拟闸门能力限制）
        spill_vol = 0.0
        if new_storage > cfg.storage_max:
            spill_vol = new_storage - cfg.storage_max
            new_storage = cfg.storage_max

        out["inflow"][t] = inflow
        out["storage"][t] = new_storage
        out["level"][t] = curve.level_of(new_storage)
        out["evaporation_volume"][t] = evap_vol
        out["eco_release"][t] = eco_vol / dt
        for name in use_names:
            out["withdrawals"][name][t] = take_vol[name] / dt
            out["deficits"][name][t] = ts.demands[name][t] - take_vol[name] / dt
        out["spill"][t] = spill_vol / dt
        out["conflicts"][t] = conflict
        # 独立核算每步水量守恒残差
        out["balance_error"][t] = (
            new_storage - storage - (in_vol - evap_vol - release_vol - spill_vol)
        )

        storage = new_storage

    out["summary"] = _summarize(out, ts, use_names)
    return out


def _summarize(out: dict, ts: TimeSeries, use_names: list[str]) -> dict:
    dt = out["dt_seconds"]

    def total(series: list[float | None]) -> float:
        return sum(v for v in series if v is not None)

    conflict_steps = [
        {"step": t, "code": code, "message": CONFLICT_MESSAGES[code]}
        for t, code in enumerate(out["conflicts"])
        if code is not None
    ]
    computed = [e for e in out["balance_error"] if e is not None]
    return {
        "total_inflow_volume": total(out["inflow"]) * dt,
        "total_evaporation_volume": total(out["evaporation_volume"]),
        "total_eco_release_volume": total(out["eco_release"]) * dt,
        "total_withdrawal_volume": {
            k: total(out["withdrawals"][k]) * dt for k in use_names
        },
        "total_deficit_volume": {
            k: total(out["deficits"][k]) * dt for k in use_names
        },
        "total_spill_volume": total(out["spill"]) * dt,
        "missing_steps": [t for t, m in enumerate(out["missing_inflow"]) if m],
        "conflict_steps": conflict_steps,
        "max_abs_balance_error": max((abs(e) for e in computed), default=0.0),
        "min_storage": min((s for s in out["storage"] if s is not None), default=None),
        "max_storage": max((s for s in out["storage"] if s is not None), default=None),
    }
