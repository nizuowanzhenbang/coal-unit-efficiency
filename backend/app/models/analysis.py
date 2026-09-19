"""对标基准 + 耗差分析 + AI 燃烧优化建议。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BenchmarkTarget(Base):
    """某机组某小指标的对标值与耗差灵敏度。

    sensitivity 表示该指标偏离基准 1 个单位会带来多少 g/kWh 的供电煤耗变化，
    是耗差分析（把运行偏差翻译成"多烧了多少煤"）的核心系数。
    """

    __tablename__ = "benchmark_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    indicator: Mapped[str] = mapped_column(String(48), index=True)  # flue_gas_temp / flue_o2 / ...
    label: Mapped[str] = mapped_column(String(64), default="")
    unit_text: Mapped[str] = mapped_column(String(16), default="")

    target_value: Mapped[float] = mapped_column(Float)             # 目标/先进值
    design_value: Mapped[float] = mapped_column(Float, default=0.0)  # 设计值
    sensitivity: Mapped[float] = mapped_column(Float, default=0.0)  # g/kWh 每单位偏差
    direction: Mapped[str] = mapped_column(String(16), default="LOWER_BETTER")  # 越低/越高越好

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class DeviationAnalysis(Base):
    """一次耗差分析的单条结果：某指标实际 vs 目标 → 折算煤耗影响。"""

    __tablename__ = "deviation_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    indicator: Mapped[str] = mapped_column(String(48), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")

    actual_value: Mapped[float] = mapped_column(Float)
    target_value: Mapped[float] = mapped_column(Float)
    deviation: Mapped[float] = mapped_column(Float)
    coal_rate_impact: Mapped[float] = mapped_column(Float)  # 折算供电煤耗影响 g/kWh（正=多烧）
    severity: Mapped[str] = mapped_column(String(16), default="NORMAL")  # NORMAL/WATCH/ALERT
    note: Mapped[str] = mapped_column(String(256), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OptimizationSuggestion(Base):
    """AI 燃烧寻优给出的一条运行调整建议。"""

    __tablename__ = "optimization_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("coal_units.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # OPT-YYYYMMDD-NNNN
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    load_mw: Mapped[float] = mapped_column(Float)
    coal_lhv: Mapped[float] = mapped_column(Float)
    current_o2: Mapped[float] = mapped_column(Float)
    recommended_o2: Mapped[float] = mapped_column(Float)
    current_flue_temp: Mapped[float] = mapped_column(Float, default=0.0)
    current_fly_ash_carbon: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_secondary_air: Mapped[str] = mapped_column(String(128), default="")
    recommended_mill_combo: Mapped[str] = mapped_column(String(128), default="")

    predicted_coal_rate_drop: Mapped[float] = mapped_column(Float)  # 预期供电煤耗下降 g/kWh
    predicted_saving_yuan_day: Mapped[float] = mapped_column(Float, default=0.0)  # 折合日省（元）
    confidence: Mapped[float] = mapped_column(Float, default=0.0)   # 0~1
    model_version: Mapped[str] = mapped_column(String(32), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING/ADOPTED/REJECTED

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
