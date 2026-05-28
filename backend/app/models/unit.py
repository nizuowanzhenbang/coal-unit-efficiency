"""机组台账：一台机组 = 锅炉 + 汽轮机 + 发电机，记录设计基准值。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CoalUnit(Base):
    __tablename__ = "coal_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # U-01
    name: Mapped[str] = mapped_column(String(128))
    capacity_mw: Mapped[float] = mapped_column(Float)                       # 额定容量 MW
    boiler_model: Mapped[str] = mapped_column(String(128), default="")
    turbine_model: Mapped[str] = mapped_column(String(128), default="")

    # 设计/铭牌基准——能效对标与耗差分析的参照系
    design_net_coal_rate: Mapped[float] = mapped_column(Float, default=300.0)  # 设计供电煤耗 g/kWh
    design_boiler_eff: Mapped[float] = mapped_column(Float, default=93.0)      # 设计锅炉效率 %
    design_pipe_eff: Mapped[float] = mapped_column(Float, default=99.0)        # 管道效率 %
    design_turbine_eff: Mapped[float] = mapped_column(Float, default=45.0)     # 汽机循环效率 %
    design_heat_rate: Mapped[float] = mapped_column(Float, default=7800.0)     # 设计热耗率 kJ/kWh
    design_aux_ratio: Mapped[float] = mapped_column(Float, default=5.5)        # 设计厂用电率 %
    design_ash_ar: Mapped[float] = mapped_column(Float, default=15.0)          # 设计收到基灰分 %
    design_coal_lhv: Mapped[float] = mapped_column(Float, default=20900.0)     # 设计入炉煤低位发热量 kJ/kg

    commission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
