"""API 路由：模拟、方案对比、场景存取。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..engine.simulate import run_simulation
from ..models.db import Scenario
from ..schemas import ScenarioInput, ScenarioMeta, SimulationResponse

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulate", response_model=SimulationResponse)
def simulate(payload: ScenarioInput):
    """不保存，直接对 1~2 个方案做固定时间步水量平衡模拟。"""
    try:
        return run_simulation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/scenarios", response_model=ScenarioMeta)
def save_scenario(payload: ScenarioInput, db: Session = Depends(get_db)):
    row = Scenario(name=payload.name, payload_json=payload.model_dump_json())
    db.add(row)
    db.commit()
    db.refresh(row)
    return ScenarioMeta(
        id=row.id,
        name=row.name,
        created_at=row.created_at.isoformat(),
        payload=payload,
    )


@router.get("/scenarios", response_model=list[ScenarioMeta])
def list_scenarios(db: Session = Depends(get_db)):
    rows = db.query(Scenario).order_by(Scenario.id.desc()).all()
    return [
        ScenarioMeta(
            id=r.id,
            name=r.name,
            created_at=r.created_at.isoformat(),
            payload=ScenarioInput.model_validate_json(r.payload_json),
        )
        for r in rows
    ]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioMeta)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    row = db.get(Scenario, scenario_id)
    if row is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    return ScenarioMeta(
        id=row.id,
        name=row.name,
        created_at=row.created_at.isoformat(),
        payload=ScenarioInput.model_validate_json(row.payload_json),
    )


@router.post("/scenarios/{scenario_id}/simulate", response_model=SimulationResponse)
def simulate_saved(scenario_id: int, db: Session = Depends(get_db)):
    row = db.get(Scenario, scenario_id)
    if row is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    payload = ScenarioInput.model_validate_json(row.payload_json)
    return run_simulation(payload, scenario_id=scenario_id)


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    row = db.get(Scenario, scenario_id)
    if row is None:
        raise HTTPException(status_code=404, detail="场景不存在")
    db.delete(row)
    db.commit()


@router.get("/health")
def health():
    return {"status": "ok", "service": "reservoir-teaching-sim"}
