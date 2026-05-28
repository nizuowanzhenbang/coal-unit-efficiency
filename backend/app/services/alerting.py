"""能效预警：带去重的告警写入。

同一机组 + 同一类别且仍 OPEN 的告警只刷新实测值与触发时间，不再新开一条，
避免持续越限刷出告警风暴。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.alert import Alert
from .codes import next_code


def raise_alert(
    db: Session,
    *,
    unit_id: int,
    category: str,
    level: str,
    title: str,
    measured_value: float = 0.0,
    threshold_value: float = 0.0,
    message: str = "",
) -> Alert:
    existing = (
        db.query(Alert)
        .filter(Alert.unit_id == unit_id, Alert.category == category, Alert.status == "OPEN")
        .order_by(Alert.triggered_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.measured_value = measured_value
        existing.threshold_value = threshold_value
        existing.level = level
        existing.title = title
        existing.message = message
        existing.triggered_at = now
        db.commit()
        db.refresh(existing)
        return existing

    alert = Alert(
        unit_id=unit_id,
        code=next_code(db, Alert, Alert.code, "AL"),
        category=category,
        level=level,
        title=title,
        measured_value=measured_value,
        threshold_value=threshold_value,
        message=message,
        status="OPEN",
        triggered_at=now,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
