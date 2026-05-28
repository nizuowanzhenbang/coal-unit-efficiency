"""APScheduler 定时作业。

三类后台任务：
  · 能效计算（默认 1 min）：补算尚未生成能效记录的最新工况；
  · 耗差扫描（默认 5 min）：对最新工况逐项耗差分析 + 触发越限告警；
  · 日报生成（每日 01:00）：为每台机组结算前一日能效报告。
内部 _xxx(db) 函数与对外 *_job() 包装分离，便于在测试里直接喂入测试库。
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models.operation import EfficiencyRecord
from .models.unit import CoalUnit
from .services import efficiency_engine, monitoring, reporting

logger = logging.getLogger("scheduler")
_scheduler: BackgroundScheduler | None = None


def _active_units(db: Session) -> list[CoalUnit]:
    return db.query(CoalUnit).filter(CoalUnit.is_active.is_(True)).all()


def _efficiency_calc(db: Session) -> int:
    processed = 0
    for unit in _active_units(db):
        snap = efficiency_engine.latest_snapshot(db, unit.id)
        if snap is None:
            continue
        exists = (
            db.query(EfficiencyRecord)
            .filter(EfficiencyRecord.snapshot_id == snap.id)
            .first()
        )
        if exists is None:
            monitoring.process_snapshot(db, unit, snap)
            processed += 1
    return processed


def _deviation_scan(db: Session) -> int:
    scanned = 0
    for unit in _active_units(db):
        snap = efficiency_engine.latest_snapshot(db, unit.id)
        if snap is None:
            continue
        record = (
            db.query(EfficiencyRecord)
            .filter(EfficiencyRecord.unit_id == unit.id)
            .order_by(EfficiencyRecord.ts.desc())
            .first()
        )
        devs = efficiency_engine.analyze_deviations(db, unit, snap, persist=True)
        if record is not None:
            monitoring._check_alerts(db, unit, record, devs)
        scanned += 1
    return scanned


def _run_daily_reports(db: Session, day: datetime | None = None) -> int:
    target = day or (datetime.now(timezone.utc) - timedelta(days=1))
    start = datetime.combine(target.date(), time.min, tzinfo=timezone.utc)
    end = datetime.combine(target.date(), time.max, tzinfo=timezone.utc)
    count = 0
    for unit in _active_units(db):
        reporting.generate_report(
            db, unit, period_type="DAILY", period_start=start, period_end=end
        )
        count += 1
    return count


def _wrap(func) -> None:
    db = SessionLocal()
    try:
        func(db)
    except Exception:  # noqa: BLE001  后台作业不让异常打断调度线程
        logger.exception("定时作业执行失败")
    finally:
        db.close()


def efficiency_calc_job() -> None:
    _wrap(_efficiency_calc)


def deviation_scan_job() -> None:
    _wrap(_deviation_scan)


def daily_report_job() -> None:
    _wrap(_run_daily_reports)


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.enable_scheduler or _scheduler is not None:
        return _scheduler
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(efficiency_calc_job, "interval", minutes=settings.efficiency_calc_interval_min, id="eff_calc")
    sched.add_job(deviation_scan_job, "interval", minutes=settings.deviation_scan_interval_min, id="dev_scan")
    sched.add_job(daily_report_job, "cron", hour=1, minute=0, id="daily_report")
    sched.start()
    _scheduler = sched
    logger.info("能效调度器已启动")
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
