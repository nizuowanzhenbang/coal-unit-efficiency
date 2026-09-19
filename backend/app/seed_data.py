"""演示种子数据：3 台不同等级机组 + 对标 + 24h 工况联动 + AI 建议 + 日报。

U-01 故意运行在"亚健康"状态（排烟温度高、氧量大、飞灰含碳量高）以触发能效告警与耗差，
U-02 / U-03 运行良好，形成对照，便于驾驶舱演示。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .algorithms import coal_consumption as cc
from .algorithms.combustion_optimizer import CombustionOptimizer
from .algorithms.deviation import DEFAULT_SENSITIVITIES
from .config import settings
from .database import SessionLocal, init_db
from .models.analysis import BenchmarkTarget, OptimizationSuggestion
from .models.operation import OperatingSnapshot
from .models.unit import CoalUnit
from .models.user import Role, User
from .security import hash_password
from .services import efficiency_engine, monitoring, reporting
from .services.codes import next_code
from .services.optimization_evidence import attach_input_evidence

DEMO_USERS = [
    ("admin", "管理员", Role.ADMIN),
    ("operator", "运行值班员", Role.OPERATOR),
    ("energyeng", "能效专工", Role.ENERGY_ENG),
    ("manager", "生产副厂长", Role.MANAGER),
    ("viewer", "访客", Role.VIEWER),
]

# 机组台账 + 典型运行工况 + 对标目标
UNIT_PROFILES = [
    {
        "code": "U-01",
        "name": "#1 亚临界燃煤机组",
        "capacity_mw": 600.0,
        "boiler_model": "SG-2008/17.5-M915",
        "turbine_model": "N600-16.7/538/538",
        "design_net_coal_rate": 305.0,
        "design_boiler_eff": 92.5,
        "design_pipe_eff": 99.0,
        "design_turbine_eff": 44.5,
        "design_heat_rate": 8050.0,
        "design_aux_ratio": 5.8,
        "design_ash_ar": 18.0,
        "design_coal_lhv": 20000.0,
        "commission": date(2009, 6, 1),
        "op": {
            "load_frac": 0.93,
            "flue_gas_temp": 146.0,
            "flue_o2": 5.2,
            "fly_ash_carbon": 4.2,
            "slag_carbon": 6.0,
            "condenser_vacuum": 5.6,
            "coal_lhv": 19700.0,
            "main_steam_temp": 533.0,
            "main_steam_press": 16.5,
            "reheat_steam_temp": 531.0,
            "feedwater_temp": 274.0,
            "aux_ratio": 6.1,
            "target_net": 315.0,
        },
        "bench": {
            "flue_gas_temp": 125.0,
            "flue_o2": 3.6,
            "fly_ash_carbon": 2.5,
            "main_steam_temp": 538.0,
            "reheat_steam_temp": 538.0,
            "condenser_vacuum": 4.9,
            "aux_ratio": 5.8,
        },
    },
    {
        "code": "U-02",
        "name": "#2 超临界燃煤机组",
        "capacity_mw": 660.0,
        "boiler_model": "HG-1913/25.4-YM4",
        "turbine_model": "N660-25/566/566",
        "design_net_coal_rate": 292.0,
        "design_boiler_eff": 93.5,
        "design_pipe_eff": 99.2,
        "design_turbine_eff": 46.0,
        "design_heat_rate": 7720.0,
        "design_aux_ratio": 5.2,
        "design_ash_ar": 14.0,
        "design_coal_lhv": 21500.0,
        "commission": date(2014, 9, 1),
        "op": {
            "load_frac": 0.95,
            "flue_gas_temp": 124.0,
            "flue_o2": 3.5,
            "fly_ash_carbon": 1.9,
            "slag_carbon": 4.0,
            "condenser_vacuum": 4.7,
            "coal_lhv": 21600.0,
            "main_steam_temp": 566.0,
            "main_steam_press": 25.0,
            "reheat_steam_temp": 565.0,
            "feedwater_temp": 290.0,
            "aux_ratio": 5.1,
            "target_net": 290.0,
        },
        "bench": {
            "flue_gas_temp": 122.0,
            "flue_o2": 3.4,
            "fly_ash_carbon": 2.0,
            "main_steam_temp": 566.0,
            "reheat_steam_temp": 566.0,
            "condenser_vacuum": 4.6,
            "aux_ratio": 5.2,
        },
    },
    {
        "code": "U-03",
        "name": "#3 超超临界燃煤机组",
        "capacity_mw": 1000.0,
        "boiler_model": "DG-2980/26.15-II",
        "turbine_model": "N1000-26.25/600/600",
        "design_net_coal_rate": 282.0,
        "design_boiler_eff": 94.0,
        "design_pipe_eff": 99.3,
        "design_turbine_eff": 47.5,
        "design_heat_rate": 7450.0,
        "design_aux_ratio": 4.6,
        "design_ash_ar": 12.0,
        "design_coal_lhv": 23000.0,
        "commission": date(2019, 11, 1),
        "op": {
            "load_frac": 0.96,
            "flue_gas_temp": 117.0,
            "flue_o2": 3.1,
            "fly_ash_carbon": 1.5,
            "slag_carbon": 3.5,
            "condenser_vacuum": 4.4,
            "coal_lhv": 23200.0,
            "main_steam_temp": 600.0,
            "main_steam_press": 26.0,
            "reheat_steam_temp": 600.0,
            "feedwater_temp": 298.0,
            "aux_ratio": 4.5,
            "target_net": 279.0,
        },
        "bench": {
            "flue_gas_temp": 118.0,
            "flue_o2": 3.0,
            "fly_ash_carbon": 1.6,
            "main_steam_temp": 600.0,
            "reheat_steam_temp": 600.0,
            "condenser_vacuum": 4.3,
            "aux_ratio": 4.6,
        },
    },
]


def _coal_flow_for(target_net: float, aux_ratio: float, load: float, lhv: float) -> float:
    """反推达到目标供电煤耗所需的入炉煤量 t/h。"""
    gross_rate = target_net * (1.0 - aux_ratio / 100.0)
    return gross_rate * cc.STD_COAL_LHV * load / (lhv * 1000.0)


def _seed_users(db: Session) -> None:
    for username, full_name, role in DEMO_USERS:
        db.add(
            User(
                username=username,
                full_name=full_name,
                role=role.value,
                hashed_password=hash_password(settings.demo_password),
            )
        )
    db.commit()


def _seed_unit(db: Session, profile: dict) -> CoalUnit:
    unit = CoalUnit(
        code=profile["code"],
        name=profile["name"],
        capacity_mw=profile["capacity_mw"],
        boiler_model=profile["boiler_model"],
        turbine_model=profile["turbine_model"],
        design_net_coal_rate=profile["design_net_coal_rate"],
        design_boiler_eff=profile["design_boiler_eff"],
        design_pipe_eff=profile["design_pipe_eff"],
        design_turbine_eff=profile["design_turbine_eff"],
        design_heat_rate=profile["design_heat_rate"],
        design_aux_ratio=profile["design_aux_ratio"],
        design_ash_ar=profile["design_ash_ar"],
        design_coal_lhv=profile["design_coal_lhv"],
        commission_date=profile["commission"],
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)

    for indicator, target in profile["bench"].items():
        meta = DEFAULT_SENSITIVITIES.get(indicator, {})
        db.add(
            BenchmarkTarget(
                unit_id=unit.id,
                indicator=indicator,
                label=meta.get("label", indicator),
                unit_text=meta.get("unit", ""),
                target_value=target,
                design_value=target,
                sensitivity=meta.get("sens", 0.0),
                direction=meta.get("direction", "LOWER_BETTER"),
            )
        )
    db.commit()
    return unit


def _seed_snapshots(db: Session, unit: CoalUnit, op: dict, hours: int = 24) -> None:
    now = datetime.now(timezone.utc)
    for i in range(hours):
        ts = now - timedelta(hours=hours - 1 - i)
        wave = math.sin(i / hours * 2 * math.pi)
        load = round(unit.capacity_mw * op["load_frac"] * (1.0 + 0.04 * wave), 1)
        target_net = op["target_net"] + 1.5 * wave
        aux_ratio = op["aux_ratio"] + 0.1 * wave
        coal_flow = round(_coal_flow_for(target_net, aux_ratio, load, op["coal_lhv"]), 2)
        snap = OperatingSnapshot(
            unit_id=unit.id,
            ts=ts,
            load_mw=load,
            main_steam_temp=round(op["main_steam_temp"] + 1.5 * wave, 1),
            main_steam_press=op["main_steam_press"],
            reheat_steam_temp=round(op["reheat_steam_temp"] + 1.5 * wave, 1),
            feedwater_temp=op["feedwater_temp"],
            flue_gas_temp=round(op["flue_gas_temp"] + 2.0 * wave, 1),
            flue_o2=round(op["flue_o2"] + 0.15 * wave, 2),
            fly_ash_carbon=round(op["fly_ash_carbon"] + 0.2 * wave, 2),
            slag_carbon=op["slag_carbon"],
            condenser_vacuum=round(op["condenser_vacuum"] + 0.1 * wave, 2),
            ambient_temp=20.0,
            coal_flow_tph=coal_flow,
            coal_lhv=op["coal_lhv"],
            aux_power_mw=round(load * aux_ratio / 100.0, 2),
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        monitoring.process_snapshot(db, unit, snap)


def _seed_optimization(db: Session, unit: CoalUnit) -> None:
    snap = efficiency_engine.latest_snapshot(db, unit.id)
    if snap is None:
        return
    optimizer = CombustionOptimizer()
    result = optimizer.recommend(
        load_mw=snap.load_mw,
        capacity_mw=unit.capacity_mw,
        current_o2=snap.flue_o2,
        current_flue_temp=snap.flue_gas_temp,
        current_fly_ash_carbon=snap.fly_ash_carbon,
    )
    attach_input_evidence(result, optimizer, unit, snap, settings.standard_coal_price)
    gen_kwh_day = snap.load_mw * 24.0 * 1000.0
    saving_t_day = result.predicted_coal_rate_drop * gen_kwh_day / 1_000_000.0
    db.add(
        OptimizationSuggestion(
            unit_id=unit.id,
            code=next_code(db, OptimizationSuggestion, OptimizationSuggestion.code, "OPT"),
            ts=datetime.now(timezone.utc),
            load_mw=snap.load_mw,
            coal_lhv=snap.coal_lhv,
            current_o2=snap.flue_o2,
            recommended_o2=result.recommended_o2,
            current_flue_temp=snap.flue_gas_temp,
            current_fly_ash_carbon=snap.fly_ash_carbon,
            recommended_secondary_air=result.secondary_air,
            recommended_mill_combo=result.mill_combo,
            predicted_coal_rate_drop=result.predicted_coal_rate_drop,
            predicted_saving_yuan_day=round(saving_t_day * settings.standard_coal_price, 2),
            confidence=result.confidence,
            model_version=result.model_version,
            rationale=result.rationale,
            evaluation={**result.evaluation, 'snapshot_id': snap.id, 'snapshot_ts': snap.ts.isoformat()},
            status="PENDING",
        )
    )
    db.commit()


def seed(db: Session) -> None:
    _seed_users(db)
    now = datetime.now(timezone.utc)
    for profile in UNIT_PROFILES:
        unit = _seed_unit(db, profile)
        _seed_snapshots(db, unit, profile["op"])
        _seed_optimization(db, unit)
        reporting.generate_report(
            db,
            unit,
            period_type="DAILY",
            period_start=now - timedelta(hours=24),
            period_end=now,
        )


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("数据已存在，跳过种子注入。")
            return
        seed(db)
        print("种子数据注入完成：3 台机组 + 72 条工况 + 能效/耗差/告警/AI建议/日报。")
    finally:
        db.close()


if __name__ == "__main__":
    run()
