"""跨系统集成入库端点（共享密钥鉴权）。

← 煤质化验系统推送各机组入炉煤最新低位发热量，缓存供工况录入时回填默认值。
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
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
