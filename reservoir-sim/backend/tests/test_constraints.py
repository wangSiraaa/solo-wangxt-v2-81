"""硬条件与冲突：最小生态流量、库容上下限、用水优先级、冲突时段定位。"""
from __future__ import annotations

import pytest

from app.engine import (CONFLICT_BELOW_MIN, CONFLICT_ECO_UNMET, ReservoirCurve,
                        simulate)

from .helpers import CURVE, DT, make_config, make_series

TOL = 1e-6


def test_eco_flow_is_always_released_when_water_available():
    """水量充足时，生态流量必须足额下泄，取水在其后分配。"""
    cfg = make_config(eco_flow=1.0)
    res = simulate(cfg, make_series(3, inflow=10.0, dem_m=2.0, dem_a=3.0), CURVE)
    for t in range(3):
        assert abs(res["eco_release"][t] - 1.0) < 1e-12
        assert res["deficits"]["municipal"][t] == 0.0
        assert res["deficits"]["agriculture"][t] == 0.0


def test_priority_decides_who_gets_water_first():
    """水量有限时，高优先级用水先被满足，低优先级承担缺口。"""
    # 可用水量只够生态(1) + 一类用水：初始 5e6，下限 1e6，零来水
    # 每步可用 = 4e6/步? 逐步衰减；这里验证"先市政、后农业"的分配顺序
    cfg = make_config(eco_flow=1.0, storage_initial=1.5e6, storage_min=1e6)
    ts = make_series(1, inflow=0.0, dem_m=3.0, dem_a=3.0)
    res = simulate(cfg, ts, CURVE)
    avail = 1.5e6 - 1e6          # 50 万 m³ 可用
    eco = 1.0 * DT               # 86400 m³
    remain = avail - eco         # 剩余给取水
    assert abs(res["withdrawals"]["municipal"][0] - min(3.0 * DT, remain) / DT) < 1e-9
    left = max(remain - 3.0 * DT, 0.0)
    assert abs(res["withdrawals"]["agriculture"][0] - left / DT) < 1e-9
    assert res["deficits"]["agriculture"][0] > 0  # 缺口落在低优先级


def test_priority_order_can_be_swapped():
    """调整优先级后，缺口应转移到另一类用水。"""
    cfg = make_config(eco_flow=0.0, storage_initial=1.2e6, storage_min=1e6,
                      priority=("agriculture", "municipal"))
    ts = make_series(1, inflow=0.0, dem_m=3.0, dem_a=3.0)
    res = simulate(cfg, ts, CURVE)
    # 可用 20 万 m³ ≈ 2.31 m³/s，全部给农业
    assert res["deficits"]["agriculture"][0] == 0.0 or res["withdrawals"]["agriculture"][0] > 0
    assert res["withdrawals"]["municipal"][0] == 0.0
    assert res["deficits"]["municipal"][0] == 3.0


def test_conflict_steps_reported_when_eco_flow_infeasible():
    """来水不足、生态流量与库容下限冲突：指出确切的冲突时段。"""
    # 初始库容 = 下限 + 0.5 步生态需水；零来水 → 第 0 步尚可部分下泄，第 1 步起冲突
    eco = 2.0
    cfg = make_config(eco_flow=eco, storage_initial=1e6 + 0.5 * eco * DT,
                      storage_min=1e6)
    res = simulate(cfg, make_series(4, inflow=0.0), CURVE)
    # 第 0 步：可用 = 0.5 步生态需水 < 生态需水 → 冲突
    assert res["conflicts"][0] == CONFLICT_ECO_UNMET
    assert all(c == CONFLICT_ECO_UNMET for c in res["conflicts"])
    steps = [c["step"] for c in res["summary"]["conflict_steps"]]
    assert steps == [0, 1, 2, 3]
    # 冲突期间库容不得跌破下限（保下限优先），生态流量只能部分下泄
    assert all(s >= 1e6 - TOL for s in res["storage"])
    assert res["eco_release"][0] < eco


def test_storage_never_exceeds_max_and_min_when_feasible():
    """可行情形下，库容始终位于上下限之间（硬条件）。"""
    cfg = make_config(eco_flow=1.0)
    ts = make_series(8, inflow=[50.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                     dem_m=1.0, dem_a=1.0)
    res = simulate(cfg, ts, CURVE)
    for s in res["storage"]:
        assert 1e6 - TOL <= s <= 9e6 + TOL


def test_unavoidable_evaporation_below_min_is_flagged():
    """蒸发损失超过可用水量：即使完全不放水也守不住下限 → 标记冲突。"""
    cfg = make_config(eco_flow=0.0, storage_initial=1e6 + 1.0, storage_min=1e6)
    # 面积 ~1e6 m² × 0.5 m = 50 万 m³ 蒸发，而库容只高出下限 1 m³
    res = simulate(cfg, make_series(1, inflow=0.0, evap=0.5), CURVE)
    assert res["conflicts"][0] == CONFLICT_BELOW_MIN
    assert res["storage"][0] < 1e6  # 物理上不可避免，诚实呈现而非伪造


def test_level_follows_storage_curve():
    """水位必须按给定库容曲线换算。"""
    res = simulate(make_config(), make_series(2, inflow=0.0), CURVE)
    for t in range(2):
        assert abs(res["level"][t] - CURVE.level_of(res["storage"][t])) < 1e-9
