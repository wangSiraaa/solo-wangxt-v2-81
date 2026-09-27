"""固定时间步水库水量平衡核心引擎。

每个时段的平衡方程（内部单位均为 m^3）：

    S_end = S_start + I - E - R_env - U - A - P

  I      入流（来水；缺测为 None，绝不补零）
  E      蒸发损失
  R_env  生态基流泄放（硬条件）
  U/A    城市/农业供水（两类用水，可设优先级）
  P      弃水（超过库容上限的部分）

硬条件：
  1) S_min <= S_end <= S_max（死库容 / 正常蓄水位库容）
  2) R_env >= 生态基流要求
若某时段"完全不供水"也无法同时满足上述两条，则该时段为结构性冲突时段。
"""
from __future__ import annotations

import numpy as np
from scipy.interpolate import interp1d

from ..schemas import (
    ConflictPeriod,
    PeriodResult,
    PriorityMode,
    ScenarioInput,
    SchemeInput,
    SchemeResult,
    SchemeSummary,
    SimulationResponse,
)
from .units import EVAP_DEPTH_FACTORS, VOLUME_FACTORS, flow_to_volume

TOL = 1e-6


def _series_to_volumes(
    ts,
    seconds: float,
    *,
    surface_area: float | None = None,
) -> list[float | None]:
    """把一个时序列换算成每时段体积 m^3；None（缺测）原样保留。ts 为 None 时返回空表。"""
    if ts is None:
        return []
    values = ts.values
    unit = ts.unit
    out: list[float | None] = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        if v < 0:
            raise ValueError("时序列不允许出现负值")
        if ts.kind == "flow":
            out.append(flow_to_volume(v, unit, seconds))
        elif ts.kind == "volume":
            factor = VOLUME_FACTORS.get(unit)
            if factor is None:
                # 体积序列只接受体积单位
                raise ValueError(f"体积序列不支持单位 {unit}")
            out.append(v * factor)
        else:  # evap
            if unit == "m3":
                out.append(v)
            elif unit in EVAP_DEPTH_FACTORS:
                area = ts.surface_area_m2 or surface_area
                if not area:
                    raise ValueError("蒸发以水深给定时必须提供水面面积 surface_area_m2")
                out.append(v * EVAP_DEPTH_FACTORS[unit] * area)
            else:
                raise ValueError(f"蒸发序列不支持单位 {unit}")
    return out


def _pad_series(values: list[float | None], n: int, fill: float = 0.0):
    if not values:
        return [fill] * n
    return values


def _level_interpolator(scenario: ScenarioInput):
    pts = sorted(scenario.level_curve, key=lambda p: p.storage_m3)
    s = np.array([p.storage_m3 for p in pts], dtype=float)
    z = np.array([p.level_m for p in pts], dtype=float)
    # 库容曲线应单调不减
    if np.any(np.diff(s) <= 0):
        raise ValueError("库容曲线的库容值必须严格递增")
    return interp1d(s, z, kind="linear", fill_value="extrapolate")


def _allocate(
    budget: float, du: float, da: float, priority: PriorityMode
) -> tuple[float, float]:
    """按两类用水的优先级分配可供水量 budget（m^3）。

    返回 (城市供水量, 农业供水量)。
    """
    budget = max(0.0, budget)
    if priority == PriorityMode.URBAN_FIRST:
        u = min(du, budget)
        a = min(da, budget - u)
    elif priority == PriorityMode.AGRICULTURE_FIRST:
        a = min(da, budget)
        u = min(du, budget - a)
    else:  # EQUAL：按需求比例同比例满足
        total = du + da
        if total <= 0:
            return 0.0, 0.0
        f = min(1.0, budget / total)
        u, a = du * f, da * f
    return u, a


def _simulate_scheme(
    scenario: ScenarioInput,
    scheme: SchemeInput,
    inflow: list[float | None],
    evap: list[float | None],
    env: list[float | None],
    level_of,
    baseline: bool = False,
) -> tuple[list[PeriodResult], list[ConflictPeriod]]:
    """对单个方案逐时段演算。

    baseline=True 时令两类用水需求恒为 0，用于判定结构性冲突
    （即使完全不供水也满足不了生态基流+死库容的时段）。
    """
    n = len(inflow)
    seconds = scenario.timestep_hours * 3600.0

    if baseline:
        urban = [0.0] * n
        agri = [0.0] * n
    else:
        urban = _pad_series(
            _series_to_volumes(scheme.urban_demand, seconds), n, 0.0
        )
        agri = _pad_series(
            _series_to_volumes(scheme.agriculture_demand, seconds), n, 0.0
        )

    smin = scenario.min_storage_m3
    smax = scenario.max_storage_m3

    periods: list[PeriodResult] = []
    conflicts: list[ConflictPeriod] = []
    storage = scenario.initial_storage_m3
    state_unknown = False  # 一旦来水缺测，其后平衡无法闭合

    for i in range(n):
        label = scenario.labels[i] if scenario.labels else None
        I = inflow[i]
        E = evap[i] if evap[i] is not None else 0.0
        R = env[i] if env[i] is not None else 0.0
        Du, Da = (0.0, 0.0) if baseline else (urban[i], agri[i])

        def _empty(warnings: list[str], *, this_inflow_missing: bool) -> PeriodResult:
            # 实测输入（本时段来水、蒸发、基流目标、需水）如实展示；
            # 但凡依赖期初库容的量（放水、供水、弃水、库容、水位）一律缺失。
            return PeriodResult(
                index=i,
                label=label,
                inflow_m3=None if this_inflow_missing else I,
                evaporation_m3=None if this_inflow_missing else E,
                env_target_m3=R,
                env_release_m3=None,
                urban_demand_m3=None if baseline else Du,
                urban_supply_m3=None,
                agriculture_demand_m3=None if baseline else Da,
                agriculture_supply_m3=None,
                spill_m3=None,
                storage_start_m3=None,
                storage_end_m3=None,
                level_end_m=None,
                balance_residual_m3=None,
                shortage_m3=None,
                feasible=True,
                missing_data=True,
                warnings=warnings,
            )

        if I is None:
            state_unknown = True
            periods.append(
                _empty(["来水缺测：本时段水量平衡无法闭合，状态缺失（不按零处理）"],
                       this_inflow_missing=True)
            )
            continue
        if state_unknown:
            periods.append(
                _empty(["此前存在来水缺测：期初库容未知，本时段平衡仍无法闭合"
                        "（实测来水如实显示，不按零处理，状态记为缺失）"],
                       this_inflow_missing=False)
            )
            continue

        s0 = storage
        warnings: list[str] = []
        avail = s0 + I - E  # 本时段可支配水量

        # ---- 硬条件可行性：生态基流 + 死库容 ----
        feasible = True
        reason = ""
        if avail - R < smin - TOL:
            feasible = False
            reason = (
                f"即使完全不供水，下泄生态基流 {R:,.0f} m³ 后库容 "
                f"{avail - R:,.0f} m³ 低于死库容 {smin:,.0f} m³"
            )
            if baseline:
                conflicts.append(
                    ConflictPeriod(
                        index=i,
                        label=label,
                        reason=reason,
                        required_m3=R + smin - s0,
                        available_m3=I - E,
                    )
                )

        if feasible:
            # 用户供水总预算：生态基流之后、维持死库容之上的可用水量
            budget = max(0.0, avail - R - smin)
            u, a = _allocate(budget, Du, Da, scheme.priority)
            # 弃水：先用城市/农业取水消落，剩余超出上限的水量必须弃掉
            spill = max(0.0, avail - R - u - a - smax)
            s1 = avail - R - u - a - spill
            env_release = R
        else:
            # 冲突时段：尽量下泄生态流量，但死守死库容；供水全部无法保证
            env_release = max(0.0, avail - smin)
            env_release = min(env_release, R)
            u = a = 0.0
            spill = max(0.0, avail - env_release - smax)
            s1 = min(smax, max(smin, avail - env_release - spill))
            warnings.append(reason)

        # ---- 水位换算（给定库容曲线，线性插值）----
        z1 = float(level_of(s1))

        # ---- 水量守恒校核 ----
        residual = s1 - s0 - I + E + env_release + u + a + spill
        if abs(residual) > 1e-4:
            warnings.append(f"水量平衡残差 {residual:.3g} m³ 超出容差")

        shortage = max(0.0, Du - u) + max(0.0, Da - a)
        if shortage > TOL:
            warnings.append(
                f"供水缺口 {shortage:,.0f} m³"
                f"（城市缺 {max(0, Du - u):,.0f}，农业缺 {max(0, Da - a):,.0f}）"
            )
        if spill > TOL:
            warnings.append(f"来水超过库容上限，弃水 {spill:,.0f} m³")
        if I == 0.0:
            warnings.append("本时段来水为 0（零来水）")

        periods.append(
            PeriodResult(
                index=i,
                label=label,
                inflow_m3=I,
                evaporation_m3=E,
                env_target_m3=R,
                env_release_m3=env_release,
                urban_demand_m3=None if baseline else Du,
                urban_supply_m3=None if baseline else u,
                agriculture_demand_m3=None if baseline else Da,
                agriculture_supply_m3=None if baseline else a,
                spill_m3=spill,
                storage_start_m3=s0,
                storage_end_m3=s1,
                level_end_m=z1,
                balance_residual_m3=residual,
                shortage_m3=shortage if not baseline else None,
                feasible=feasible,
                missing_data=False,
                warnings=warnings,
            )
        )
        storage = s1

    return periods, conflicts


def _summarize(name: str, scheme: SchemeInput, periods: list[PeriodResult]) -> SchemeSummary:
    def total(attr: str):
        # 按已知值累加：缺失时段该字段为 None 时跳过（合计仅覆盖已知数据，不补零）
        vals = [v for v in (getattr(p, attr) for p in periods) if v is not None]
        return float(sum(vals)) if vals else None

    known = [p for p in periods if not p.missing_data]
    last_known = known[-1] if known else None
    levels = [p.level_end_m for p in known if p.level_end_m is not None]

    return SchemeSummary(
        name=name,
        priority=scheme.priority,
        total_inflow_m3=total("inflow_m3"),
        total_evap_m3=total("evaporation_m3"),
        total_env_release_m3=total("env_release_m3"),
        total_urban_supply_m3=total("urban_supply_m3"),
        total_ag_supply_m3=total("agriculture_supply_m3"),
        total_spill_m3=total("spill_m3"),
        total_demand_m3=(
            None
            if total("urban_demand_m3") is None
            else (total("urban_demand_m3") or 0.0) + (total("agriculture_demand_m3") or 0.0)
        ),
        total_shortage_m3=total("shortage_m3"),
        final_storage_m3=last_known.storage_end_m3 if last_known else None,
        max_level_m=max(levels) if levels else None,
        feasible_periods=sum(1 for p in periods if p.feasible and not p.missing_data),
        infeasible_periods=[p.index for p in periods if not p.feasible],
        missing_periods=[p.index for p in periods if p.missing_data],
        spill_periods=[p.index for p in periods if (p.spill_m3 or 0.0) > TOL],
    )


def run_simulation(scenario: ScenarioInput, scenario_id: int | None = None) -> SimulationResponse:
    n = len(scenario.inflow.values)
    seconds = scenario.timestep_hours * 3600.0

    inflow = _series_to_volumes(scenario.inflow, seconds)
    evap = _pad_series(
        _series_to_volumes(scenario.evaporation, seconds, surface_area=None), n, 0.0
    )

    # 方案级生态流量可覆盖场景级
    def env_for(scheme: SchemeInput):
        ts = scheme.environmental_flow or scenario.environmental_flow
        return _pad_series(_series_to_volumes(ts, seconds), n, 0.0)

    level_of = _level_interpolator(scenario)

    # Pass A：零供水基线，判定结构性冲突时段
    baseline_scheme = SchemeInput(name="__baseline__", priority=PriorityMode.EQUAL)
    _, conflicts = _simulate_scheme(
        scenario, baseline_scheme, inflow, evap,
        env_for(baseline_scheme), level_of, baseline=True,
    )

    # Pass B：逐方案按优先级演算
    results: list[SchemeResult] = []
    for scheme in scenario.schemes:
        periods, _ = _simulate_scheme(
            scenario, scheme, inflow, evap, env_for(scheme), level_of, baseline=False
        )
        results.append(
            SchemeResult(
                summary=_summarize(scheme.name, scheme, periods),
                periods=periods,
            )
        )

    return SimulationResponse(
        scenario_id=scenario_id,
        timestep_hours=scenario.timestep_hours,
        n_periods=n,
        schemes=results,
        conflicts=conflicts,
    )
