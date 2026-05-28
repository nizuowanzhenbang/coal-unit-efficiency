"""能效报告：生成、查看、签发。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models.report import EnergyReport
from ..models.unit import CoalUnit
from ..models.user import Role, User
from ..schemas import ReportGenerateRequest, ReportOut
from ..services import reporting

router = APIRouter(prefix="/reports", tags=["能效报告"])
_eng = require_roles(Role.ENERGY_ENG)


@router.get("", response_model=list[ReportOut])
def list_reports(
    unit_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[EnergyReport]:
    q = db.query(EnergyReport)
    if unit_id is not None:
        q = q.filter(EnergyReport.unit_id == unit_id)
    return q.order_by(EnergyReport.created_at.desc()).limit(min(limit, 500)).all()


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> EnergyReport:
    report = db.get(EnergyReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    return report


@router.post("/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate(payload: ReportGenerateRequest, db: Session = Depends(get_db), _: User = Depends(_eng)) -> EnergyReport:
    unit = db.get(CoalUnit, payload.unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="机组不存在")
    return reporting.generate_report(
        db,
        unit,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        target_rate=payload.target_rate,
    )


@router.post("/{report_id}/issue", response_model=ReportOut)
def issue(report_id: int, db: Session = Depends(get_db), _: User = Depends(_eng)) -> EnergyReport:
    report = db.get(EnergyReport, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    report.status = "ISSUED"
    db.commit()
    db.refresh(report)
    return report
