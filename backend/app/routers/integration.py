"""跨系统集成入库端点（共享密钥鉴权）。

← 煤质化验系统推送各机组入炉煤最新低位发热量，缓存供工况录入时回填默认值。
"""

from __future__ import annotations

import math
from datetime import timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models.user import Role, User
from ..models.unit import CoalUnit
from ..models.operation import OperatingSnapshot
from ..services.efficiency_engine import compute_record
from ..services.coal_quality_adapter import CoalQualityPreview, adapt
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/integration", tags=["跨系统集成"])

# unit_code -> 最新入炉煤低位发热量 kJ/kg
_fuel_cache: dict[str, float] = {}


class CoalLhvPush(BaseModel):
    unit_code: str
    coal_lhv: float


def _verify(secret: str | None) -> None:
    if secret != settings.integration_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="集成密钥无效")


@router.get("/health")
def health() -> dict:
    return {"service": "coal-unit-efficiency", "status": "ok", "cached_units": len(_fuel_cache)}


@router.post("/coal-lhv")
def receive_coal_lhv(
    payload: CoalLhvPush, x_integration_secret: str | None = Header(default=None)
) -> dict:
    _verify(x_integration_secret)
    _fuel_cache[payload.unit_code] = payload.coal_lhv
    return {"ok": True, "unit_code": payload.unit_code, "coal_lhv": payload.coal_lhv}


@router.get("/coal-lhv/{unit_code}")
def get_cached_lhv(unit_code: str) -> dict:
    return {"unit_code": unit_code, "coal_lhv": _fuel_cache.get(unit_code)}


@router.post('/coal-quality-preview')
def preview_coal_quality(
    payload: CoalQualityPreview,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.OPERATOR, Role.ENERGY_ENG)),
) -> dict:
    """用户指定批次的情景估算，保留来源；不自动认定为实际入炉煤。"""
    unit = db.query(CoalUnit).filter(CoalUnit.code == payload.allocation.unit_code).first()
    if unit is None:
        raise HTTPException(status_code=404, detail='关联机组不存在')
    if payload.conditions.load_mw > unit.capacity_mw:
        raise HTTPException(status_code=422, detail='情景负荷超过机组额定容量')
    heat, lineage = adapt(payload)
    data = payload.conditions.model_dump()
    data['ts'] = data['ts'].astimezone(timezone.utc)
    snapshot = OperatingSnapshot(unit_id=unit.id, coal_lhv=heat, **data)
    record = compute_record(unit, snapshot)
    efficiency = {column.name: getattr(record, column.name) for column in record.__table__.columns
                  if column.name not in {'id', 'unit_id', 'snapshot_id', 'ts', 'created_at'}}
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in efficiency.values()):
        raise HTTPException(status_code=422, detail='当前工况或机组参数无法形成有限计算结果')
    return {'mode': 'scenario_preview', 'unit_code': unit.code, 'coal_lhv_kj_kg': heat,
            'lineage': lineage, 'efficiency': efficiency}
