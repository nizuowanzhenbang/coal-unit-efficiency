"""运行工况快照 + 能效计算结果（时序）。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OperatingSnapshot(Base):
    """一条 DCS 运行工况采样。能效引擎据此反算各项指标。"""

    __tablename__ = "operating_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    load_mw: Mapped[float] = mapped_column(Float)                  # 机组负荷 MW
    main_steam_temp: Mapped[float] = mapped_column(Float)          # 主蒸汽温度 ℃
    main_steam_press: Mapped[float] = mapped_column(Float)         # 主蒸汽压力 MPa
    reheat_steam_temp: Mapped[float] = mapped_column(Float)        # 再热蒸汽温度 ℃
    feedwater_temp: Mapped[float] = mapped_column(Float)           # 给水温度 ℃
    flue_gas_temp: Mapped[float] = mapped_column(Float)            # 排烟温度 ℃
    flue_o2: Mapped[float] = mapped_column(Float)                  # 烟气含氧量 %（干基）
    fly_ash_carbon: Mapped[float] = mapped_column(Float)           # 飞灰含碳量 %
    slag_carbon: Mapped[float] = mapped_column(Float, default=5.0)  # 炉渣含碳量 %
    condenser_vacuum: Mapped[float] = mapped_column(Float)         # 凝汽器真空（绝压 kPa，越低越好）
    ambient_temp: Mapped[float] = mapped_column(Float, default=20.0)  # 环境温度 ℃

    coal_flow_tph: Mapped[float] = mapped_column(Float)            # 入炉煤量 t/h
    coal_lhv: Mapped[float] = mapped_column(Float)                 # 入炉煤低位发热量 kJ/kg
    aux_power_mw: Mapped[float] = mapped_column(Float)             # 厂用电功率 MW

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EfficiencyRecord(Base):
    """能效引擎对某条/某段工况算出的结果。"""

    __tablename__ = "efficiency_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("operating_snapshots.id"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    load_mw: Mapped[float] = mapped_column(Float)

    gross_coal_rate: Mapped[float] = mapped_column(Float)  # 发电煤耗 g/kWh
    net_coal_rate: Mapped[float] = mapped_column(Float)    # 供电煤耗 g/kWh（核心 KPI）
    boiler_eff: Mapped[float] = mapped_column(Float)       # 锅炉效率 %
    pipe_eff: Mapped[float] = mapped_column(Float)         # 管道效率 %
    turbine_eff: Mapped[float] = mapped_column(Float)      # 汽机循环效率 %
    gross_eff: Mapped[float] = mapped_column(Float)        # 发电效率 %
    net_eff: Mapped[float] = mapped_column(Float)          # 供电效率 %
    heat_rate: Mapped[float] = mapped_column(Float)        # 机组热耗率 kJ/kWh
    aux_ratio: Mapped[float] = mapped_column(Float)        # 厂用电率 %
    excess_air: Mapped[float] = mapped_column(Float)       # 过量空气系数

    q2: Mapped[float] = mapped_column(Float, default=0.0)  # 排烟热损失 %
    q3: Mapped[float] = mapped_column(Float, default=0.0)  # 化学不完全燃烧损失 %
    q4: Mapped[float] = mapped_column(Float, default=0.0)  # 机械不完全燃烧损失 %
    q5: Mapped[float] = mapped_column(Float, default=0.0)  # 散热损失 %
    q6: Mapped[float] = mapped_column(Float, default=0.0)  # 灰渣物理热损失 %

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
