"""能效计算引擎：把一条工况快照算成完整能效画像 + 耗差清单。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..algorithms import boiler_efficiency as be
from ..algorithms import coal_consumption as cc
from ..algorithms import deviation as dv
from ..models.analysis import BenchmarkTarget, DeviationAnalysis
from ..models.operation import EfficiencyRecord, OperatingSnapshot
from ..models.unit import CoalUnit

# 工况快照字段 → 耗差指标的映射（厂用电率单独算）
_SNAPSHOT_INDICATORS = (
    "flue_gas_temp",
    "flue_o2",
    "fly_ash_carbon",
    "main_steam_temp",
    "reheat_steam_temp",
    "condenser_vacuum",
)


def compute_record(unit: CoalUnit, snap: OperatingSnapshot) -> EfficiencyRecord:
    """对单条快照做反平衡 + 煤耗换算，返回未入库的 EfficiencyRecord。"""
    boiler = be.boiler_efficiency(
        flue_gas_temp=snap.flue_gas_temp,
        ambient_temp=snap.ambient_temp,
        flue_o2=snap.flue_o2,
        ash_ar=unit.design_ash_ar,
        coal_lhv=snap.coal_lhv,
        fly_ash_carbon=snap.fly_ash_carbon,
        slag_carbon=snap.slag_carbon,
        load_mw=snap.load_mw,
        capacity_mw=unit.capacity_mw,
    )

    aux_ratio = (snap.aux_power_mw / snap.load_mw * 100.0) if snap.load_mw > 0 else 0.0
    gross_rate = cc.gross_coal_rate_measured(snap.coal_flow_tph, snap.coal_lhv, snap.load_mw)
    net_rate = cc.net_coal_rate(gross_rate, aux_ratio)

    gross_eff = (cc.IDEAL_COAL_RATE / gross_rate * 100.0) if gross_rate > 0 else 0.0
    pipe_eff = unit.design_pipe_eff
    denom = boiler.efficiency * pipe_eff
    turbine_eff = (gross_eff * 10000.0 / denom) if denom > 0 else 0.0
    net_eff = gross_eff * (1.0 - aux_ratio / 100.0)
    heat_rate = cc.heat_rate_from_eff(gross_eff)

    return EfficiencyRecord(
        unit_id=unit.id,
        snapshot_id=snap.id,
        ts=snap.ts,
        load_mw=snap.load_mw,
        gross_coal_rate=round(gross_rate, 3),
        net_coal_rate=round(net_rate, 3),
        boiler_eff=boiler.efficiency,
        pipe_eff=round(pipe_eff, 3),
        turbine_eff=round(turbine_eff, 3),
        gross_eff=round(gross_eff, 3),
        net_eff=round(net_eff, 3),
        heat_rate=round(heat_rate, 1),
        aux_ratio=round(aux_ratio, 3),
        excess_air=boiler.excess_air,
        q2=boiler.q2,
        q3=boiler.q3,
        q4=boiler.q4,
        q5=boiler.q5,
        q6=boiler.q6,
    )


def _benchmark_map(db: Session, unit_id: int) -> dict[str, BenchmarkTarget]:
    rows = db.query(BenchmarkTarget).filter(BenchmarkTarget.unit_id == unit_id).all()
    return {b.indicator: b for b in rows}


def analyze_deviations(
    db: Session, unit: CoalUnit, snap: OperatingSnapshot, persist: bool = True
) -> list[DeviationAnalysis]:
    """对快照逐项做耗差分析，可选落库。"""
    benches = _benchmark_map(db, unit.id)
    aux_ratio = (snap.aux_power_mw / snap.load_mw * 100.0) if snap.load_mw > 0 else 0.0
    actuals = {ind: getattr(snap, ind) for ind in _SNAPSHOT_INDICATORS}
    actuals["aux_ratio"] = aux_ratio

    results: list[DeviationAnalysis] = []
    now = datetime.now(timezone.utc)
    for indicator, actual in actuals.items():
        bench = benches.get(indicator)
        if bench is None:
            continue
        res = dv.analyze_indicator(
            indicator,
            actual,
            bench.target_value,
            sensitivity=bench.sensitivity or None,
            direction=bench.direction,
            label=bench.label or None,
            unit=bench.unit_text or None,
        )
        row = DeviationAnalysis(
            unit_id=unit.id,
            ts=now,
            indicator=res.indicator,
            label=res.label,
            actual_value=res.actual,
            target_value=res.target,
            deviation=res.deviation,
            coal_rate_impact=res.coal_rate_impact,
            severity=res.severity,
        )
        results.append(row)
        if persist:
            db.add(row)
    if persist:
        db.commit()
        for r in results:
            db.refresh(r)
    return results


def latest_snapshot(db: Session, unit_id: int) -> OperatingSnapshot | None:
    return (
        db.query(OperatingSnapshot)
        .filter(OperatingSnapshot.unit_id == unit_id)
        .order_by(OperatingSnapshot.ts.desc())
        .first()
    )
