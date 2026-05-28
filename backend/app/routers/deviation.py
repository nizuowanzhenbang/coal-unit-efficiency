"""耗差分析：基于最新工况即时分析，或查历史。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.analysis import DeviationAnalysis
from ..models.unit import CoalUnit
from ..models.user import Role, User
from ..schemas import DeviationOut
from ..services import efficiency_engine

router = APIRouter(prefix="/deviations", tags=["耗差分析"])
_operator = require_roles(Role.OPERATOR, Role.ENERGY_ENG)


@router.get("", response_model=list[DeviationOut])
def list_deviations(
    unit_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DeviationAnalysis]:
    q = db.query(DeviationAnalysis)
    if unit_id is not None:
        q = q.filter(DeviationAnalysis.unit_id == unit_id)
    return q.order_by(DeviationAnalysis.ts.desc()).limit(min(limit, 1000)).all()


@router.post("/analyze/{unit_id}", response_model=list[DeviationOut])
def analyze_now(
    unit_id: int, db: Session = Depends(get_db), _: User = Depends(_operator)
) -> list[DeviationAnalysis]:
    unit = db.get(CoalUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机组不存在")
    snap = efficiency_engine.latest_snapshot(db, unit_id)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该机组暂无工况数据")
    return efficiency_engine.analyze_deviations(db, unit, snap, persist=True)
