"""人工声明的煤批次到机组情景关联，不代表实际消耗。"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CoalScenarioAllocation(Base):
    __tablename__ = 'coal_scenario_allocations'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    source_instance: Mapped[str] = mapped_column(String(128), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(16), nullable=False)
    valid_from: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_to: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
