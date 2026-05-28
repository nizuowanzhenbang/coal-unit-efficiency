"""能效报告：日报/月报，含节煤量、节约金额、减碳量。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EnergyReport(Base):
    __tablename__ = "energy_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # ER-YYYYMM-NN
    period_type: Mapped[str] = mapped_column(String(16), default="DAILY")   # DAILY/MONTHLY
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    avg_net_coal_rate: Mapped[float] = mapped_column(Float)     # 实际平均供电煤耗 g/kWh
    target_net_coal_rate: Mapped[float] = mapped_column(Float)  # 对标目标 g/kWh
    coal_rate_deviation: Mapped[float] = mapped_column(Float)   # 偏差 g/kWh
    avg_boiler_eff: Mapped[float] = mapped_column(Float, default=0.0)
    avg_heat_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_aux_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    total_gen_mwh: Mapped[float] = mapped_column(Float, default=0.0)  # 周期发电量 MWh

    coal_saving_t: Mapped[float] = mapped_column(Float, default=0.0)    # 较目标节标煤量 t（正=节约）
    cost_saving_yuan: Mapped[float] = mapped_column(Float, default=0.0)  # 节约金额 元
    co2_reduction_t: Mapped[float] = mapped_column(Float, default=0.0)   # 减碳量 t

    top_deviations: Mapped[str] = mapped_column(Text, default="[]")  # 主要耗差项 JSON
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")  # DRAFT/ISSUED

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
