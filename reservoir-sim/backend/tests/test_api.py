"""API 端到端：场景保存（数据库）、读取、运行、两方案对比。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

from .helpers import scenario_payload

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_simulate_inline():
    p = scenario_payload(inflow=[10.0, None, 5.0, 0.0], eco_flow=1.0,
                         demands={"municipal": [2.0] * 4, "agriculture": [1.0] * 4})
    r = client.post("/api/simulate", json=p)
    assert r.status_code == 200
    res = r.json()["result"]
    assert res["n_steps"] == 4
    assert res["storage"][1] is None            # 缺测时段为缺失
    assert res["missing_inflow"] == [False, True, False, False]
    assert res["summary"]["max_abs_balance_error"] < 1e-6


def test_scenario_crud_and_run():
    p = scenario_payload(name="方案A", inflow=[20.0] * 4, eco_flow=1.0,
                         demands={"municipal": [3.0] * 4, "agriculture": [2.0] * 4})
    r = client.post("/api/scenarios", json=p)
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.get("/api/scenarios")
    assert any(s["id"] == sid for s in r.json())

    r = client.get(f"/api/scenarios/{sid}")
    assert r.json()["payload"]["name"] == "方案A"

    r = client.post(f"/api/scenarios/{sid}/run")
    assert r.status_code == 200
    assert r.json()["result"]["summary"]["max_abs_balance_error"] < 1e-6


def test_compare_two_scenarios():
    a = scenario_payload(name="低优先农业", eco_flow=1.0, inflow=[4.0] * 4,
                         storage_initial=2e6,
                         demands={"municipal": [2.0] * 4, "agriculture": [3.0] * 4},
                         priority=["municipal", "agriculture"])
    b = scenario_payload(name="高优先农业", eco_flow=1.0, inflow=[4.0] * 4,
                         storage_initial=2e6,
                         demands={"municipal": [2.0] * 4, "agriculture": [3.0] * 4},
                         priority=["agriculture", "municipal"])
    id_a = client.post("/api/scenarios", json=a).json()["id"]
    id_b = client.post("/api/scenarios", json=b).json()["id"]

    r = client.post("/api/compare", json={"a_id": id_a, "b_id": id_b})
    assert r.status_code == 200
    body = r.json()
    assert body["a"]["name"] == "低优先农业"
    # 两种优先级下总缺口应此消彼长：B 方案农业缺口更小、市政缺口更大
    da = body["a"]["result"]["summary"]["total_deficit_volume"]
    db = body["b"]["result"]["summary"]["total_deficit_volume"]
    assert db["agriculture"] <= da["agriculture"] + 1e-6
    assert db["municipal"] >= da["municipal"] - 1e-6
    assert "total_spill_volume" in body["diff"]


def test_compare_with_inline_scenario():
    a = scenario_payload(name="内联A", inflow=[10.0] * 4)
    b = scenario_payload(name="内联B", inflow=[0.0] * 4)
    r = client.post("/api/compare", json={"a": a, "b": b})
    assert r.status_code == 200
    assert r.json()["diff"]["total_spill_volume"] >= 0


def test_validation_rejects_bad_priority():
    p = scenario_payload(priority=["municipal", "municipal"])
    r = client.post("/api/simulate", json=p)
    assert r.status_code == 422


def test_validation_rejects_initial_out_of_bounds():
    p = scenario_payload(storage_initial=1e7)  # 超过上限 9e6
    r = client.post("/api/simulate", json=p)
    assert r.status_code == 422
