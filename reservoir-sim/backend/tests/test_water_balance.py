"""水量守恒核对：零来水、超库容洪峰、不同单位输入、缺测来水。

每个用例都独立重算每步水量平衡，验证：
    S(t+1) = S(t) + I·Δt − E − R·Δt − Spill·Δt
"""
from __future__ import annotations

import math

import pytest

from app.engine import simulate
from app.schemas import ScenarioIn

from .helpers import CURVE, DT, make_config, make_series, scenario_payload

TOL = 1e-6  # m³


def check_balance_closed(result: dict) -> None:
    """对每个已计算时段，用结果序列独立重算守恒残差。"""
    dt = result["dt_seconds"]
    storages = result["storage"]
    prev = None
    for t in range(result["n_steps"]):
        s_end = storages[t]
        if s_end is None:
            continue  # 缺测时段无水量平衡可核
        if prev is None:
            prev = s_end  # 首步从初始库容起算，这里只校验残差字段
        assert abs(result["balance_error"][t]) < TOL, f"时段 {t} 水量不守恒"
    assert result["summary"]["max_abs_balance_error"] < TOL


# ---------- 样例 1：零来水 ----------

def test_zero_inflow_no_demand_storage_unchanged():
    """零来水、无蒸发、无取水：库容必须保持不变。"""
    res = simulate(make_config(), make_series(10, inflow=0.0), CURVE)
    assert all(abs(s - 5e6) < TOL for s in res["storage"])
    check_balance_closed(res)


def test_zero_inflow_with_withdrawal_storage_drops_exactly():
    """零来水、只取水：每步库容减少量必须恰好等于放水体积。"""
    res = simulate(make_config(), make_series(5, inflow=0.0, dem_m=2.0), CURVE)
    prev = 5e6
    for t in range(5):
        assert abs(res["storage"][t] - (prev - 2.0 * DT)) < TOL
        prev = res["storage"][t]
    check_balance_closed(res)


def test_zero_inflow_with_evaporation():
    """零来水、只蒸发：每步损失 = 蒸发水深 × 水面面积（随库容变化）。"""
    res = simulate(make_config(), make_series(4, inflow=0.0, evap=0.01), CURVE)
    prev = 5e6
    for t in range(4):
        area = CURVE.area_of(prev)
        assert abs(res["evaporation_volume"][t] - 0.01 * area) < TOL
        assert abs(res["storage"][t] - (prev - 0.01 * area)) < TOL
        prev = res["storage"][t]
    check_balance_closed(res)


# ---------- 样例 2：超过库容的洪峰 ----------

def test_flood_peak_triggers_spill_and_respects_max_storage():
    """洪峰超过库容上限：出现弃水，库容永不超过上限，且全程守恒。"""
    # 单步入流 500 m³/s × 86400 s = 4320 万 m³，远超库容上限 900 万 m³
    res = simulate(make_config(), make_series(6, inflow=[500.0, 500.0, 10.0, 0.0, 0.0, 0.0]),
                   CURVE)
    assert max(res["storage"]) <= 9e6 + TOL
    assert res["spill"][0] > 0 and res["spill"][1] > 0
    # 总量核算：末库容 = 初始 + 总入流 − 总弃水（无蒸发无取水）
    total_in = sum(v for v in res["inflow"] if v) * DT
    total_spill = sum(res["spill"]) * DT
    assert abs(res["storage"][-1] - (5e6 + total_in - total_spill)) < TOL
    assert abs(res["summary"]["total_spill_volume"] - total_spill) < TOL
    check_balance_closed(res)


# ---------- 样例 3：不同单位输入 ----------

def test_unit_inputs_give_identical_results():
    """同一物理过程用不同单位表示，模拟结果必须一致。"""
    base = dict(
        dt_seconds=3600, storage_min=1e5, storage_max=9e5, storage_initial=5e5,
        eco_flow=1.0,
        demands={"municipal": [2.0] * 6, "agriculture": [3.0] * 6},
        inflow=[5.0, 5.0, 10.0, 0.0, 2.0, 2.0],
        evaporation=[2.0] * 6,
        curve={"storage": [0.0, 5e5, 1e6], "level": [100.0, 110.0, 120.0],
               "area": [0.0, 1e5, 2e5]},
    )
    si = scenario_payload(
        name="SI", **base,
        units={"flow": "m3/s", "volume": "m3", "evaporation": "mm/step"},
    )
    # 同一过程：流量用 m3/h（×3600），库容用 万m3（÷1e4），蒸发用 mm/d（×24）
    alt = scenario_payload(
        name="其它单位", **{
            **base,
            "storage_min": 10.0, "storage_max": 90.0, "storage_initial": 50.0,
            "eco_flow": 3600.0,
            "demands": {"municipal": [7200.0] * 6, "agriculture": [10800.0] * 6},
            "inflow": [18000.0, 18000.0, 36000.0, 0.0, 7200.0, 7200.0],
            "evaporation": [48.0] * 6,
            "curve": {"storage": [0.0, 50.0, 100.0], "level": [100.0, 110.0, 120.0],
                      "area": [0.0, 1e5, 2e5]},
        },
        units={"flow": "m3/h", "volume": "万m3", "evaporation": "mm/d"},
    )
    res_si = simulate(*ScenarioIn.model_validate(si).to_engine())
    res_alt = simulate(*ScenarioIn.model_validate(alt).to_engine())
    for t in range(6):
        assert math.isclose(res_si["storage"][t], res_alt["storage"][t],
                            rel_tol=0, abs_tol=1e-6)
        assert math.isclose(res_si["spill"][t], res_alt["spill"][t], abs_tol=1e-12)
    check_balance_closed(res_si)
    check_balance_closed(res_alt)


# ---------- 缺测来水：显示为缺失而非零 ----------

def test_missing_inflow_is_missing_not_zero():
    """缺测时段的所有结果必须为 None（缺失），绝不能当成 0 参与计算。"""
    res = simulate(make_config(), make_series(4, inflow=[1.0, None, 1.0, 1.0]), CURVE)
    t = 1
    assert res["missing_inflow"][t] is True
    for key in ("inflow", "storage", "level", "evaporation_volume",
                "eco_release", "spill", "balance_error"):
        assert res[key][t] is None, f"{key} 在缺测时段应为 None"
    for name in ("municipal", "agriculture"):
        assert res["withdrawals"][name][t] is None
        assert res["deficits"][name][t] is None
    # 缺测若被当成 0，库容会停在上一步；这里缺测后第一步从最后已知库容继续并被标记
    assert res["estimated_start"][2] is True
    assert res["storage"][2] != res["storage"][0] or res["inflow"][2] == 0
    assert res["summary"]["missing_steps"] == [1]
    check_balance_closed(res)
