"""AI 燃烧优化建议：基于最新工况 + 历史样本寻优。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..algorithms.combustion_optimizer import CombustionOptimizer
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.analysis import OptimizationSuggestion
from ..models.operation import EfficiencyRecord, OperatingSnapshot
from ..models.unit import CoalUnit
from ..models.user import Role, User
from ..schemas import OptimizationOut, OptimizationStatusUpdate, OptimizeRequest
from ..services import efficiency_engine
from ..services.codes import next_code

router = APIRouter(prefix="/optimization", tags=["AI燃烧优化"])
_eng = require_roles(Role.ENERGY_ENG)


def _history_samples(db: Session, unit_id: int, limit: int = 500) -> list[dict]:
    rows = (
        db.query(EfficiencyRecord, OperatingSnapshot)
        .join(OperatingSnapshot, EfficiencyRecord.snapshot_id == OperatingSnapshot.id)
        .filter(EfficiencyRecord.unit_id == unit_id)
        .order_by(EfficiencyRecord.ts.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "load_mw": s.load_mw,
            "flue_o2": s.flue_o2,
            "flue_gas_temp": s.flue_gas_temp,
            "fly_ash_carbon": s.fly_ash_carbon,
            "net_coal_rate": r.net_coal_rate,
        }
        for r, s in rows
    ]


@router.get("", response_model=list[OptimizationOut])
def list_suggestions(
    unit_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[OptimizationSuggestion]:
    q = db.query(OptimizationSuggestion)
    if unit_id is not None:
        q = q.filter(OptimizationSuggestion.unit_id == unit_id)
    return q.order_by(OptimizationSuggestion.ts.desc()).limit(min(limit, 500)).all()


@router.post("/generate", response_model=OptimizationOut, status_code=status.HTTP_201_CREATED)
def generate(payload: OptimizeRequest, db: Session = Depends(get_db), _: User = Depends(_eng)) -> OptimizationSuggestion:
    unit = db.get(CoalUnit, payload.unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机组不存在")
    snap = efficiency_engine.latest_snapshot(db, unit.id)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该机组暂无工况数据")

    optimizer = CombustionOptimizer()
    if payload.use_history:
        optimizer.fit(_history_samples(db, unit.id))
    result = optimizer.recommend(
        load_mw=snap.load_mw,
        capacity_mw=unit.capacity_mw,
        current_o2=snap.flue_o2,
        current_flue_temp=snap.flue_gas_temp,
        current_fly_ash_carbon=snap.fly_ash_carbon,
    )

    # 折算日省金额：日发电量 × 煤耗降幅 → 节标煤 → 金额
    gen_kwh_day = snap.load_mw * 24.0 * 1000.0
    saving_t_day = result.predicted_coal_rate_drop * gen_kwh_day / 1_000_000.0
    saving_yuan_day = round(saving_t_day * settings.standard_coal_price, 2)

    suggestion = OptimizationSuggestion(
        unit_id=unit.id,
        code=next_code(db, OptimizationSuggestion, OptimizationSuggestion.code, "OPT"),
        ts=datetime.now(timezone.utc),
        load_mw=snap.load_mw,
        coal_lhv=snap.coal_lhv,
        current_o2=snap.flue_o2,
        recommended_o2=result.recommended_o2,
        current_flue_temp=snap.flue_gas_temp,
        current_fly_ash_carbon=snap.fly_ash_carbon,
        recommended_secondary_air=result.secondary_air,
        recommended_mill_combo=result.mill_combo,
        predicted_coal_rate_drop=result.predicted_coal_rate_drop,
        predicted_saving_yuan_day=saving_yuan_day,
        confidence=result.confidence,
        model_version=result.model_version,
        rationale=result.rationale,
        status="PENDING",
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.patch("/{sugg_id}", response_model=OptimizationOut)
def update_status(
    sugg_id: int,
    payload: OptimizationStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_eng),
) -> OptimizationSuggestion:
    row = db.get(OptimizationSuggestion, sugg_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="建议不存在")
    row.status = payload.status
    db.commit()
    db.refresh(row)
    return row
