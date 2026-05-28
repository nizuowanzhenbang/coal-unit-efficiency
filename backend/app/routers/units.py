"""机组台账 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.unit import CoalUnit
from ..models.user import Role, User
from ..schemas import UnitCreate, UnitOut, UnitUpdate

router = APIRouter(prefix="/units", tags=["机组"])
_eng = require_roles(Role.ENERGY_ENG)


@router.get("", response_model=list[UnitOut])
def list_units(
    active_only: bool = False, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[CoalUnit]:
    q = db.query(CoalUnit)
    if active_only:
        q = q.filter(CoalUnit.is_active.is_(True))
    return q.order_by(CoalUnit.code).all()


@router.get("/{unit_id}", response_model=UnitOut)
def get_unit(unit_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> CoalUnit:
    unit = db.get(CoalUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机组不存在")
    return unit


@router.post("", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def create_unit(payload: UnitCreate, db: Session = Depends(get_db), _: User = Depends(_eng)) -> CoalUnit:
    if db.query(CoalUnit).filter(CoalUnit.code == payload.code).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="机组编号已存在")
    unit = CoalUnit(**payload.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.patch("/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: int, payload: UnitUpdate, db: Session = Depends(get_db), _: User = Depends(_eng)
) -> CoalUnit:
    unit = db.get(CoalUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机组不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, key, value)
    db.commit()
    db.refresh(unit)
    return unit
