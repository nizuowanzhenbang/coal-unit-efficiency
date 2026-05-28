"""能效记录查询与趋势。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models.operation import EfficiencyRecord
from ..models.user import User
from ..schemas import EfficiencyOut

router = APIRouter(prefix="/efficiency", tags=["能效指标"])


@router.get("", response_model=list[EfficiencyOut])
def list_records(
    unit_id: int | None = None,
    limit: int = 300,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[EfficiencyRecord]:
    q = db.query(EfficiencyRecord)
    if unit_id is not None:
        q = q.filter(EfficiencyRecord.unit_id == unit_id)
    return q.order_by(EfficiencyRecord.ts.desc()).limit(min(limit, 2000)).all()


@router.get("/trend/{unit_id}")
def trend(
    unit_id: int, limit: int = 96, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict:
    rows = (
        db.query(EfficiencyRecord)
        .filter(EfficiencyRecord.unit_id == unit_id)
        .order_by(EfficiencyRecord.ts.desc())
        .limit(min(limit, 2000))
        .all()
    )
    rows = list(reversed(rows))
    return {
        "ts": [r.ts.isoformat() for r in rows],
        "net_coal_rate": [r.net_coal_rate for r in rows],
        "gross_coal_rate": [r.gross_coal_rate for r in rows],
        "boiler_eff": [r.boiler_eff for r in rows],
        "heat_rate": [r.heat_rate for r in rows],
        "load_mw": [r.load_mw for r in rows],
    }
