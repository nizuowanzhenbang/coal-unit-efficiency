"""APScheduler 定时作业测试（直接喂测试库）。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.analysis import BenchmarkTarget, DeviationAnalysis
from app.models.operation import EfficiencyRecord, OperatingSnapshot
from app.models.report import EnergyReport
from app.scheduler import _deviation_scan, _efficiency_calc, _run_daily_reports


def _raw_snapshot(db, unit_id, **kw):
    defaults = dict(
        unit_id=unit_id, ts=datetime.now(timezone.utc), load_mw=560.0, main_steam_temp=538.0,
        main_steam_press=16.7, reheat_steam_temp=538.0, feedwater_temp=275.0, flue_gas_temp=130.0,
        flue_o2=4.0, fly_ash_carbon=3.0, slag_carbon=5.0, condenser_vacuum=4.9, ambient_temp=20.0,
        coal_flow_tph=245.0, coal_lhv=21000.0, aux_power_mw=31.0,
    )
    defaults.update(kw)
    snap = OperatingSnapshot(**defaults)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def test_efficiency_calc_processes_unprocessed(db, unit_factory):
    unit = unit_factory()
    _raw_snapshot(db, unit.id)
    processed = _efficiency_calc(db)
    assert processed == 1
    assert db.query(EfficiencyRecord).filter(EfficiencyRecord.unit_id == unit.id).count() == 1


def test_efficiency_calc_skips_already_processed(db, unit_factory):
    unit = unit_factory()
    _raw_snapshot(db, unit.id)
    _efficiency_calc(db)
    # 第二次没有新工况 → 不重复处理
    assert _efficiency_calc(db) == 0


def test_deviation_scan(db, unit_factory):
    unit = unit_factory()
    from app.algorithms.deviation import DEFAULT_SENSITIVITIES

    meta = DEFAULT_SENSITIVITIES["flue_gas_temp"]
    db.add(BenchmarkTarget(unit_id=unit.id, indicator="flue_gas_temp", label=meta["label"],
                           unit_text=meta["unit"], target_value=125.0, sensitivity=meta["sens"],
                           direction=meta["direction"]))
    db.commit()
    _raw_snapshot(db, unit.id, flue_gas_temp=145.0)
    _efficiency_calc(db)
    scanned = _deviation_scan(db)
    assert scanned == 1
    assert db.query(DeviationAnalysis).filter(DeviationAnalysis.unit_id == unit.id).count() >= 1


def test_run_daily_reports(db, unit_factory):
    unit = unit_factory()
    _raw_snapshot(db, unit.id)
    _efficiency_calc(db)
    count = _run_daily_reports(db, day=datetime.now(timezone.utc))
    assert count == 1
    assert db.query(EnergyReport).filter(EnergyReport.unit_id == unit.id).count() == 1


def test_scheduler_jobs_ignore_units_without_data(db, unit_factory):
    unit_factory()
    assert _efficiency_calc(db) == 0
    assert _deviation_scan(db) == 0
