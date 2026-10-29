"""跨系统集成入库端点（共享密钥鉴权）。

← 煤质化验系统推送各机组入炉煤最新低位发热量，缓存供工况录入时回填默认值。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.user import Role, User
from ..models.unit import CoalUnit
from ..models.coal_association import CoalScenarioAllocation
from ..models.operation import OperatingSnapshot
from ..services.efficiency_engine import compute_record
from ..services.coal_quality_adapter import (CoalQualityPreview, Conditions, ContractModel, Identity,
                                             Measurement, SafeAwareDatetime, adapt, utc_text)
from pydantic import BaseModel, BeforeValidator, Field, ValidationError, field_validator, model_validator

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


def sanitize_nonfinite(value):
    # 保证无效输入的422详情可以编码，且不把无穷数字当成有效声明。
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        return None
    if isinstance(value, list):
        return [sanitize_nonfinite(item) for item in value]
    if isinstance(value, dict):
        return {(key if not any(0xD800 <= ord(char) <= 0xDFFF for char in key)
                 else '__invalid_unicode_key__'): sanitize_nonfinite(item)
                for key, item in value.items()}
    return value


class AllocationCreate(ContractModel):
    request_id: UUID
    source_instance: Identity
    batch_id: Identity
    unit_code: Annotated[Identity, Field(max_length=16)]
    valid_from: SafeAwareDatetime
    valid_to: SafeAwareDatetime
    evidence: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator('source_instance', 'batch_id', 'unit_code', 'evidence')
    @classmethod
    def storable_text(cls, value):
        if '\x00' in value:
            raise ValueError('文本不能包含零字符')
        if not value.strip():
            raise ValueError('文本不能为空')
        return value

    @model_validator(mode='after')
    def window(self):
        if self.valid_from >= self.valid_to:
            raise ValueError('关联结束时间必须晚于开始时间')
        return self


class SavedPreview(ContractModel):
    allocation_id: Annotated[int, Field(ge=1, le=9223372036854775807)]
    measurement: Measurement
    conditions: Conditions


def allocation_dict(row: CoalScenarioAllocation) -> dict:
    return {'id': row.id, 'kind': 'scenario', 'request_id': row.request_id,
            'source_instance': row.source_instance, 'batch_id': row.batch_id,
            'unit_code': row.unit_code, 'valid_from': row.valid_from, 'valid_to': row.valid_to,
            'evidence': row.evidence, 'created_by': row.created_by, 'created_at': row.created_at}


def same_request(row: CoalScenarioAllocation, data: dict) -> bool:
    return all(getattr(row, key) == value for key, value in data.items())


@router.post('/coal-quality-allocations', status_code=201)
def create_coal_allocation(
    payload: Annotated[AllocationCreate, BeforeValidator(sanitize_nonfinite)], response: Response, db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.OPERATOR, Role.ENERGY_ENG)),
) -> dict:
    data = {'request_id': str(payload.request_id), 'source_instance': payload.source_instance,
            'batch_id': payload.batch_id, 'unit_code': payload.unit_code,
            'valid_from': utc_text(payload.valid_from), 'valid_to': utc_text(payload.valid_to),
            'evidence': payload.evidence, 'created_by': user.username}
    existing = db.query(CoalScenarioAllocation).filter_by(request_id=data['request_id']).first()
    if existing:
        if not same_request(existing, data):
            raise HTTPException(status_code=409, detail='请求标识已用于不同的情景声明')
        response.status_code = 200
        return allocation_dict(existing)
    if not db.query(CoalUnit).filter_by(code=payload.unit_code).first():
        raise HTTPException(status_code=404, detail='关联机组不存在')
    row = CoalScenarioAllocation(**data, created_at=utc_text(datetime.now(timezone.utc)))
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(CoalScenarioAllocation).filter_by(request_id=data['request_id']).first()
        if existing and same_request(existing, data):
            response.status_code = 200
            return allocation_dict(existing)
        raise HTTPException(status_code=409, detail='情景声明请求冲突') from exc
    db.refresh(row)
    return allocation_dict(row)


@router.get('/coal-quality-allocations')
def list_coal_allocations(
    source_instance: Annotated[Identity, BeforeValidator(sanitize_nonfinite), Query()],
    batch_id: Annotated[Identity, BeforeValidator(sanitize_nonfinite), Query()],
    before_id: Annotated[int | None, Query(ge=1, le=9223372036854775807)] = None,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> dict:
    if '\x00' in source_instance or '\x00' in batch_id:
        raise HTTPException(status_code=422, detail='来源标识不能包含零字符')
    query = db.query(CoalScenarioAllocation).filter_by(source_instance=source_instance, batch_id=batch_id)
    if before_id is not None:
        query = query.filter(CoalScenarioAllocation.id < before_id)
    rows = query.order_by(CoalScenarioAllocation.id.desc()).limit(101).all()
    truncated = len(rows) > 100
    return {'items': [allocation_dict(row) for row in rows[:100]], 'truncated': truncated,
            'next_before_id': rows[99].id if truncated else None}


@router.get('/coal-quality-allocations/{allocation_id}')
def read_coal_allocation(
    allocation_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
) -> dict:
    row = db.get(CoalScenarioAllocation, allocation_id)
    if row is None:
        raise HTTPException(status_code=404, detail='情景关联不存在')
    return allocation_dict(row)


@router.post('/coal-quality-preview/saved')
def preview_saved_allocation(
    payload: Annotated[SavedPreview, BeforeValidator(sanitize_nonfinite)], db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.OPERATOR, Role.ENERGY_ENG)),
) -> dict:
    row = db.get(CoalScenarioAllocation, payload.allocation_id)
    if row is None:
        raise HTTPException(status_code=404, detail='情景关联不存在')
    try:
        combined = CoalQualityPreview.model_validate({
            'contract_version': 'coal-quality-energy/v1', 'measurement': payload.measurement,
            'allocation': {'source_instance': row.source_instance, 'batch_id': row.batch_id,
                           'unit_code': row.unit_code, 'valid_from': row.valid_from, 'valid_to': row.valid_to},
            'conditions': payload.conditions,
        })
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail='情景关联与测量或工况不一致') from exc
    result = preview_coal_quality(combined, db=db, _=user)
    result['association_id'] = row.id
    return result
