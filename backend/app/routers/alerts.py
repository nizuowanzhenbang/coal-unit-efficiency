"""能效预警查询与处置。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.alert import Alert
from ..models.user import Role, User
from ..schemas import AlertOut, AlertStatusUpdate

router = APIRouter(prefix="/alerts", tags=["能效预警"])
_handler = require_roles(Role.OPERATOR, Role.ENERGY_ENG, Role.MANAGER)


@router.get("", response_model=list[AlertOut])
def list_alerts(
    unit_id: int | None = None,
    status_filter: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Alert]:
    q = db.query(Alert)
    if unit_id is not None:
        q = q.filter(Alert.unit_id == unit_id)
    if status_filter:
        q = q.filter(Alert.status == status_filter)
    return q.order_by(Alert.triggered_at.desc()).limit(min(limit, 1000)).all()


@router.patch("/{alert_id}", response_model=AlertOut)
def update_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_handler),
) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    alert.status = payload.status
    alert.closed_at = datetime.now(timezone.utc) if payload.status == "CLOSED" else None
    db.commit()
    db.refresh(alert)
    return alert
