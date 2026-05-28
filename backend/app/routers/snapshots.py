"""运行工况快照：录入即触发能效计算与告警联动。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.operation import OperatingSnapshot
from ..models.unit import CoalUnit
from ..models.user import Role, User
from ..schemas import EfficiencyOut, SnapshotCreate, SnapshotOut
from ..services import efficiency_engine, monitoring

router = APIRouter(prefix="/snapshots", tags=["运行工况"])
_operator = require_roles(Role.OPERATOR, Role.ENERGY_ENG)


@router.get("", response_model=list[SnapshotOut])
def list_snapshots(
    unit_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[OperatingSnapshot]:
    q = db.query(OperatingSnapshot)
    if unit_id is not None:
        q = q.filter(OperatingSnapshot.unit_id == unit_id)
    return q.order_by(OperatingSnapshot.ts.desc()).limit(min(limit, 1000)).all()


@router.post("", response_model=EfficiencyOut, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    payload: SnapshotCreate, db: Session = Depends(get_db), _: User = Depends(_operator)
) -> object:
    unit = db.get(CoalUnit, payload.unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机组不存在")
    data = payload.model_dump(exclude_none=True)
    snap = OperatingSnapshot(**data)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    record, _devs = monitoring.process_snapshot(db, unit, snap)
    return record


@router.get("/latest/{unit_id}", response_model=SnapshotOut)
def latest(unit_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> OperatingSnapshot:
    snap = efficiency_engine.latest_snapshot(db, unit_id)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该机组暂无工况数据")
    return snap
