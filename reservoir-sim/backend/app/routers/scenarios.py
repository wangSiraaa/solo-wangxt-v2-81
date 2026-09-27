"""场景管理：保存 / 列表 / 读取 / 删除 / 运行已保存场景。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine import simulate
from ..models import Scenario
from ..schemas import ScenarioIn, ScenarioOut

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _to_out(s: Scenario) -> ScenarioOut:
    return ScenarioOut(
        id=s.id,
        name=s.name,
        description=s.description,
        created_at=s.created_at.isoformat() if s.created_at else None,
    )


@router.post("", response_model=ScenarioOut, status_code=201)
def create_scenario(scn: ScenarioIn, db: Session = Depends(get_db)):
    row = Scenario(name=scn.name, description=scn.description,
                   payload=scn.model_dump(mode="json"))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_db)):
    return [_to_out(s) for s in db.query(Scenario).order_by(Scenario.id).all()]


@router.get("/{scenario_id}")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    row = db.get(Scenario, scenario_id)
    if row is None:
        raise HTTPException(404, "场景不存在")
    return {**_to_out(row).model_dump(), "payload": row.payload}


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    row = db.get(Scenario, scenario_id)
    if row is None:
        raise HTTPException(404, "场景不存在")
    db.delete(row)
    db.commit()


@router.post("/{scenario_id}/run")
def run_scenario(scenario_id: int, db: Session = Depends(get_db)):
    row = db.get(Scenario, scenario_id)
    if row is None:
        raise HTTPException(404, "场景不存在")
    scn = ScenarioIn.model_validate(row.payload)
    cfg, ts, curve = scn.to_engine()
    return {"scenario": _to_out(row).model_dump(), "result": simulate(cfg, ts, curve)}
