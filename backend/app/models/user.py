"""用户与角色。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Role(StrEnum):
    ADMIN = "ADMIN"            # 系统管理员
    OPERATOR = "OPERATOR"      # 运行值班员：录工况、看实时
    ENERGY_ENG = "ENERGY_ENG"  # 能效专工：对标维护、采纳优化建议、签发报告
    MANAGER = "MANAGER"        # 生产管理者：看板、报告、告警审阅
    VIEWER = "VIEWER"          # 只读访客


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default=Role.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
