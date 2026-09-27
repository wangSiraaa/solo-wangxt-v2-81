"""模拟与方案对比。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine import simulate
from ..models import Scenario
from ..schemas import CompareRequest, ScenarioIn

router = APIRouter(prefix="/api", tags=["simulate"])


def _run(scn: ScenarioIn) -> dict:
    cfg, ts, curve = scn.to_engine()
    return simulate(cfg, ts, curve)


@router.post("/simulate")
def run_simulation(scn: ScenarioIn):
    """直接运行一个场景（不保存）。返回逐时段结果与守恒校验。"""
    return {"name": scn.name, "result": _run(scn)}


def _load(req_id: int | None, inline: ScenarioIn | None,
          db: Session) -> tuple[str, ScenarioIn]:
    if inline is not None:
        return inline.name, inline
    row = db.get(Scenario, req_id)
    if row is None:
        raise HTTPException(404, f"场景 {req_id} 不存在")
    return row.name, ScenarioIn.model_validate(row.payload)


@router.post("/compare")
def compare(req: CompareRequest, db: Session = Depends(get_db)):
    """对比两个供水方案：分别模拟，并给出关键指标差异（B − A）。"""
    name_a, scn_a = _load(req.a_id, req.a, db)
    name_b, scn_b = _load(req.b_id, req.b, db)
    res_a, res_b = _run(scn_a), _run(scn_b)

    sa, sb = res_a["summary"], res_b["summary"]
    uses = sorted(set(sa["total_deficit_volume"]) | set(sb["total_deficit_volume"]))
    diff = {
        "total_deficit_volume": {
            k: sb["total_deficit_volume"].get(k, 0.0) - sa["total_deficit_volume"].get(k, 0.0)
            for k in uses
        },
        "total_spill_volume": sb["total_spill_volume"] - sa["total_spill_volume"],
        "total_eco_release_volume":
            sb["total_eco_release_volume"] - sa["total_eco_release_volume"],
        "n_conflict_steps": {
            "a": len(sa["conflict_steps"]), "b": len(sb["conflict_steps"]),
        },
        "min_storage": {"a": sa["min_storage"], "b": sb["min_storage"]},
    }
    return {
        "a": {"name": name_a, "result": res_a},
        "b": {"name": name_b, "result": res_b},
        "diff": diff,
    }
