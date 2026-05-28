"""能效预警。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # AL-YYYYMMDD-NNNN
    category: Mapped[str] = mapped_column(String(32), index=True)  # COAL_RATE/DEVIATION/BOILER_EFF...
    level: Mapped[str] = mapped_column(String(16), default="WARNING")  # INFO/WARNING/CRITICAL
    title: Mapped[str] = mapped_column(String(128))
    measured_value: Mapped[float] = mapped_column(Float, default=0.0)
    threshold_value: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN/ACKED/CLOSED

    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
