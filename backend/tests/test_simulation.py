"""逐时段水量守恒与边界样例核对。

覆盖题目要求的三类样例：
  1) 零来水
  2) 超过库容的洪峰
  3) 不同单位输入
以及缺测来水、结构性冲突时段、两类用水优先级对比。
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.engine.simulate import run_simulation
from app.main import app
from app.schemas import (
    CurvePoint,
    PriorityMode,
    ScenarioInput,
    SchemeInput,
    TimeSeriesInput,
)


# ---------- 构造工具 ----------

def curve():
    # 死库容 10 万 m3（水位 100m），正常蓄水位库容 100 万 m3（水位 120m）
    return [
        CurvePoint(storage_m3=0, level_m=90.0),
        CurvePoint(storage_m3=100_000, level_m=100.0),
        CurvePoint(storage_m3=500_000, level_m=112.0),
        CurvePoint(storage_m3=1_000_000, level_m=120.0),
    ]


def make_scenario(inflow, schemes, *, evap=None, env=None, labels=None,
                  init=500_000.0, smin=100_000.0, smax=1_000_000.0,
                  inflow_unit="m3", timestep_hours=24.0):
    return ScenarioInput(
        name="测试场景",
        timestep_hours=timestep_hours,
        labels=labels or [f"t{i+1}" for i in range(len(inflow))],
        initial_storage_m3=init,
        min_storage_m3=smin,
        max_storage_m3=smax,
        level_curve=curve(),
        inflow=TimeSeriesInput(values=inflow, unit=inflow_unit, kind="volume" if inflow_unit in ("m3", "10^4m3", "10^8m3") else "flow"),
        evaporation=TimeSeriesInput(values=evap, unit="m3", kind="evap") if evap else None,
        environmental_flow=TimeSeriesInput(values=env, unit="m3", kind="volume") if env else None,
        schemes=schemes,
    )


def demands(urban, agri):
    return SchemeInput(
        name="方案A",
        priority=PriorityMode.URBAN_FIRST,
        urban_demand=TimeSeriesInput(values=urban, unit="m3", kind="volume"),
        agriculture_demand=TimeSeriesInput(values=agri, unit="m3", kind="volume"),
    )


# ---------- 1. 零来水 ----------

def test_zero_inflow_conservation_and_storage_floor():
    # 3 个时段零来水；每天城市用水 20 万 m3，无生态基流
    sch = demands([200_000, 200_000, 200_000], [0, 0, 0])
    sc = make_scenario([0.0, 0.0, 0.0], [sch])
    resp = run_simulation(sc)
    ps = resp.schemes[0].periods

    # 每个时段守恒残差为 0
    for p in ps:
        assert p.inflow_m3 == 0.0
        assert math.isclose(p.balance_residual_m3, 0.0, abs_tol=1e-6)
        assert p.storage_end_m3 >= 100_000.0 - 1e-6  # 不低于死库容

    # 库容轨迹：50w -> 30w -> 10w -> 10w（第三时段只能供 0）
    assert math.isclose(ps[0].storage_end_m3, 300_000, abs_tol=1e-6)
    assert math.isclose(ps[1].storage_end_m3, 100_000, abs_tol=1e-6)
    assert math.isclose(ps[2].urban_supply_m3, 0.0, abs_tol=1e-6)
    assert math.isclose(ps[2].shortage_m3, 200_000, abs_tol=1e-6)
    assert ps[2].feasible  # 硬条件（死库容）仍满足，只是供水缺口
    assert any("来水为 0" in w for w in ps[0].warnings)


# ---------- 2. 洪峰超库容 ----------

def test_flood_peak_spills_and_never_exceeds_capacity():
    # 初始 80 万，单时段来水 100 万 m3 -> 必须弃掉 80 万
    sch = demands([0], [0])
    sc = make_scenario([1_000_000.0], [sch], init=800_000.0)
    resp = run_simulation(sc)
    p = resp.schemes[0].periods[0]

    assert math.isclose(p.spill_m3, 800_000, abs_tol=1e-6)
    assert math.isclose(p.storage_end_m3, 1_000_000, abs_tol=1e-6)
    assert math.isclose(p.balance_residual_m3, 0.0, abs_tol=1e-6)
    assert math.isclose(p.level_end_m, 120.0, abs_tol=1e-9)  # 恰为正常蓄水位


def test_flood_withdraw_reduces_spill():
    # 同样洪峰，但城市取水 30 万 -> 弃水相应减少 30 万（先取水后弃水）
    sch = demands([300_000], [0])
    sc = make_scenario([1_000_000.0], [sch], init=800_000.0)
    resp = run_simulation(sc)
    p = resp.schemes[0].periods[0]
    assert math.isclose(p.spill_m3, 500_000, abs_tol=1e-6)
    assert math.isclose(p.urban_supply_m3, 300_000, abs_tol=1e-6)
    assert math.isclose(p.storage_end_m3, 1_000_000, abs_tol=1e-6)


def test_multi_period_running_conservation():
    # 随机体量的多时段守恒：总量核对
    inflow = [50_000, 200_000, 1_500_000, 0, 80_000]
    evap = [2_000, 3_000, 4_000, 1_000, 2_000]
    env = [10_000] * 5
    sch = SchemeInput(
        name="方案",
        urban_demand=TimeSeriesInput(values=[40_000] * 5, unit="m3", kind="volume"),
        agriculture_demand=TimeSeriesInput(values=[60_000] * 5, unit="m3", kind="volume"),
    )
    sc = make_scenario(inflow, [sch], evap=evap, env=env)
    resp = run_simulation(sc)
    ps = resp.schemes[0].periods

    s0 = 500_000.0
    for p in ps:
        assert math.isclose(
            p.storage_end_m3,
            p.storage_start_m3 + p.inflow_m3 - p.evaporation_m3
            - p.env_release_m3 - p.urban_supply_m3 - p.agriculture_supply_m3
            - p.spill_m3,
            abs_tol=1e-4,
        )
        assert 100_000.0 - 1e-6 <= p.storage_end_m3 <= 1_000_000.0 + 1e-6
        assert p.env_release_m3 >= 10_000.0 - 1e-6
    # 全程总量守恒
    s_end = ps[-1].storage_end_m3
    tot_in = sum(p.inflow_m3 for p in ps)
    tot_out = sum(
        p.evaporation_m3 + p.env_release_m3 + p.urban_supply_m3
        + p.agriculture_supply_m3 + p.spill_m3 for p in ps
    )
    assert math.isclose(s_end, s0 + tot_in - tot_out, abs_tol=1e-4)


# ---------- 3. 不同单位输入 ----------

def test_flow_unit_m3s_conversion_daily():
    # 1 m3/s 持续一天 = 86400 m3
    sch = demands([0], [0])
    sc = make_scenario([1.0], [sch], inflow_unit="m3/s", timestep_hours=24)
    resp = run_simulation(sc)
    assert math.isclose(resp.schemes[0].periods[0].inflow_m3, 86_400, rel_tol=1e-9)


def test_volume_unit_wan_m3():
    # 50 万 m3 以 "10^4m3" 给：50
    sch = demands([0], [0])
    sc = make_scenario([50.0], [sch], inflow_unit="10^4m3", init=900_000.0)
    resp = run_simulation(sc)
    p = resp.schemes[0].periods[0]
    assert math.isclose(p.inflow_m3, 500_000)
    assert math.isclose(p.balance_residual_m3, 0.0, abs_tol=1e-6)


def test_evap_depth_requires_area():
    from app.schemas import ScenarioInput as SI
    with pytest.raises(Exception):
        SI(
            name="x", timestep_hours=24,
            initial_storage_m3=500_000, min_storage_m3=100_000, max_storage_m3=1_000_000,
            level_curve=curve(),
            inflow=TimeSeriesInput(values=[100.0], unit="m3", kind="volume"),
            evaporation=TimeSeriesInput(values=[5.0], unit="mm", kind="evap"),
            schemes=[demands([0], [0])],
        )


def test_evap_mm_conversion_conservation():
    # 1 mm 蒸发 * 100 万 m2 水面 = 1000 m3
    sc = ScenarioInput(
        name="蒸发水深", timestep_hours=24,
        initial_storage_m3=500_000, min_storage_m3=100_000, max_storage_m3=1_000_000,
        level_curve=curve(),
        inflow=TimeSeriesInput(values=[10_000.0], unit="m3", kind="volume"),
        evaporation=TimeSeriesInput(values=[1.0], unit="mm", kind="evap",
                                    surface_area_m2=1_000_000),
        schemes=[demands([0], [0])],
    )
    resp = run_simulation(sc)
    p = resp.schemes[0].periods[0]
    assert math.isclose(p.evaporation_m3, 1_000.0)
    assert math.isclose(p.storage_end_m3, 509_000.0, abs_tol=1e-6)


# ---------- 4. 缺测来水：缺失而非零 ----------

def test_missing_inflow_is_null_not_zero():
    sch = demands([10_000, 10_000, 10_000], [0, 0, 0])
    sc = make_scenario([100_000.0, None, 50_000.0], [sch])
    resp = run_simulation(sc)
    ps = resp.schemes[0].periods

    assert ps[0].inflow_m3 == 100_000.0
    assert ps[1].missing_data is True
    assert ps[1].inflow_m3 is None      # 本时段缺测，不是 0
    assert ps[1].storage_end_m3 is None
    assert ps[1].balance_residual_m3 is None
    assert any("缺测" in w for w in ps[1].warnings)
    # 缺测之后期初库容不可知：状态量缺失，但实测来水仍如实显示
    assert ps[2].missing_data is True
    assert ps[2].inflow_m3 == 50_000.0  # 实测值不被抹零
    assert ps[2].storage_end_m3 is None
    assert ps[2].env_release_m3 is None
    assert resp.schemes[0].summary.missing_periods == [1, 2]


# ---------- 5. 结构性冲突时段 ----------

def test_structural_conflict_period_reported():
    # 初始正好死库容，零来水，却要求 5 万生态基流 -> 即使不供水也不可能
    sch = demands([0], [0])
    sc = make_scenario([0.0], [sch], env=[50_000.0], init=100_000.0)
    resp = run_simulation(sc)

    assert len(resp.conflicts) == 1
    c = resp.conflicts[0]
    assert c.index == 0
    assert "死库容" in c.reason
    p = resp.schemes[0].periods[0]
    assert p.feasible is False
    # 死守死库容：实际只能下泄 0
    assert math.isclose(p.env_release_m3, 0.0, abs_tol=1e-9)
    assert math.isclose(p.storage_end_m3, 100_000, abs_tol=1e-6)


def test_no_conflict_when_enough_water():
    sch = demands([0], [0])
    sc = make_scenario([200_000.0], [sch], env=[50_000.0], init=100_000.0)
    resp = run_simulation(sc)
    assert resp.conflicts == []
    p = resp.schemes[0].periods[0]
    assert p.feasible is True
    assert math.isclose(p.env_release_m3, 50_000.0)


# ---------- 6. 优先级：两方案对比 ----------

def test_priority_schemes_comparison():
    # 可供城市+农业总预算 100 万；城市需 80 万、农业需 80 万
    def scheme(priority):
        return SchemeInput(
            name=priority.value, priority=priority,
            urban_demand=TimeSeriesInput(values=[800_000.0], unit="m3", kind="volume"),
            agriculture_demand=TimeSeriesInput(values=[800_000.0], unit="m3", kind="volume"),
        )

    sc = make_scenario(
        [1_100_000.0],  # 初始50w + 来水110w - 死库容10w = 预算150w... 会触发弃水
        [scheme(PriorityMode.URBAN_FIRST), scheme(PriorityMode.AGRICULTURE_FIRST)],
        init=500_000.0,
    )
    resp = run_simulation(sc)
    urban_first, ag_first = resp.schemes

    # 预算 = 50w + 110w - 10w = 150w，城市优先：城市 80w、农业 70w
    p = urban_first.periods[0]
    assert math.isclose(p.urban_supply_m3, 800_000, abs_tol=1e-6)
    assert math.isclose(p.agriculture_supply_m3, 700_000, abs_tol=1e-6)
    # 农业优先反之
    q = ag_first.periods[0]
    assert math.isclose(q.agriculture_supply_m3, 800_000, abs_tol=1e-6)
    assert math.isclose(q.urban_supply_m3, 700_000, abs_tol=1e-6)
    # 两方案总供水相同（缺口都为 10 万），只是分担对象不同
    assert math.isclose(
        p.urban_supply_m3 + p.agriculture_supply_m3,
        q.urban_supply_m3 + q.agriculture_supply_m3,
        abs_tol=1e-6,
    )
    assert math.isclose(p.balance_residual_m3, 0.0, abs_tol=1e-6)
    assert math.isclose(q.balance_residual_m3, 0.0, abs_tol=1e-6)


def test_equal_priority_proportional():
    sch = SchemeInput(
        name="等权", priority=PriorityMode.EQUAL,
        urban_demand=TimeSeriesInput(values=[300_000.0], unit="m3", kind="volume"),
        agriculture_demand=TimeSeriesInput(values=[900_000.0], unit="m3", kind="volume"),
    )
    # 预算 60 万 -> 同比例 50%
    sc = make_scenario([200_000.0], [sch], init=500_000.0)
    p = run_simulation(sc).schemes[0].periods[0]
    assert math.isclose(p.urban_supply_m3, 150_000, abs_tol=1e-6)
    assert math.isclose(p.agriculture_supply_m3, 450_000, abs_tol=1e-6)


# ---------- 7. API 与 PostgreSQL 持久化（本地以 SQLite 执行） ----------

@pytest.fixture(scope="module", autouse=True)
def _setup_db(tmp_path_factory):
    # 每个测试进程用独立 sqlite
    import app.database as dbmod
    dbmod.engine.dispose()
    dbmod.Base.metadata.create_all(bind=dbmod.engine)
    yield


client = TestClient(app)


def test_api_simulate_and_save_roundtrip():
    payload = make_scenario([0.0, 500_000.0], [demands([100_000, 100_000], [0, 0])]).model_dump()
    r = client.post("/api/simulate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["disclaimer"]
    assert len(data["schemes"]) == 1

    r2 = client.post("/api/scenarios", json=payload)
    assert r2.status_code == 200
    sid = r2.json()["id"]

    r3 = client.get(f"/api/scenarios/{sid}")
    assert r3.status_code == 200
    assert r3.json()["payload"]["inflow"]["values"] == [0.0, 500_000.0]

    r4 = client.post(f"/api/scenarios/{sid}/simulate")
    assert r4.status_code == 200
    assert r4.json()["scenario_id"] == sid

    assert client.delete(f"/api/scenarios/{sid}").status_code == 204
    assert client.get(f"/api/scenarios/{sid}").status_code == 404


def test_api_rejects_bad_curve_coverage():
    good = make_scenario([1.0], [demands([0], [0])]).model_dump()
    # 构造时曲线合法，发请求前改成盖不住库容上限的曲线
    good["level_curve"] = [
        {"storage_m3": 0, "level_m": 90.0},
        {"storage_m3": 400_000, "level_m": 110.0},
    ]
    r = client.post("/api/simulate", json=good)
    assert r.status_code == 422
