"""不可变的操作者提交测量版本；不证明来源真实性。"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

class CoalMeasurementEvidence(Base):
    __tablename__ = 'coal_measurement_evidence'
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
