"""对标基准管理（能效专工维护）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.analysis import BenchmarkTarget
from ..models.user import Role, User
from ..schemas import BenchmarkCreate, BenchmarkOut, BenchmarkUpdate

router = APIRouter(prefix="/benchmarks", tags=["对标基准"])
_eng = require_roles(Role.ENERGY_ENG)


@router.get("", response_model=list[BenchmarkOut])
def list_benchmarks(
    unit_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[BenchmarkTarget]:
    q = db.query(BenchmarkTarget)
    if unit_id is not None:
        q = q.filter(BenchmarkTarget.unit_id == unit_id)
    return q.order_by(BenchmarkTarget.unit_id, BenchmarkTarget.indicator).all()


@router.post("", response_model=BenchmarkOut, status_code=status.HTTP_201_CREATED)
def upsert_benchmark(
    payload: BenchmarkCreate, db: Session = Depends(get_db), _: User = Depends(_eng)
) -> BenchmarkTarget:
    existing = (
        db.query(BenchmarkTarget)
        .filter(
            BenchmarkTarget.unit_id == payload.unit_id,
            BenchmarkTarget.indicator == payload.indicator,
        )
        .first()
    )
    if existing is not None:
        for key, value in payload.model_dump().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    row = BenchmarkTarget(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{bench_id}", response_model=BenchmarkOut)
def update_benchmark(
    bench_id: int, payload: BenchmarkUpdate, db: Session = Depends(get_db), _: User = Depends(_eng)
) -> BenchmarkTarget:
    row = db.get(BenchmarkTarget, bench_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对标项不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{bench_id}")
def delete_benchmark(bench_id: int, db: Session = Depends(get_db), _: User = Depends(_eng)) -> dict:
    row = db.get(BenchmarkTarget, bench_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return {"deleted": True}
