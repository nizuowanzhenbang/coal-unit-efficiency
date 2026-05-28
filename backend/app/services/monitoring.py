"""工况入库后的联动编排：算能效 → 做耗差 → 触发告警 → 跨系统推送。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.alert import Alert
from ..models.analysis import DeviationAnalysis
from ..models.operation import EfficiencyRecord, OperatingSnapshot
from ..models.unit import CoalUnit
from . import efficiency_engine, integration_client
from .alerting import raise_alert

COAL_RATE_WARN_MARGIN = 5.0   # 供电煤耗超设计值多少 g/kWh 触发预警
COAL_RATE_CRIT_MARGIN = 12.0
BOILER_EFF_MARGIN = 2.0       # 锅炉效率低于设计值多少个百分点触发预警
TOTAL_DEVIATION_THRESHOLD = 8.0  # 耗差合计 g/kWh 阈值


def _has_open(db: Session, unit_id: int, category: str) -> bool:
    return (
        db.query(Alert)
        .filter(Alert.unit_id == unit_id, Alert.category == category, Alert.status == "OPEN")
        .first()
        is not None
    )


def _check_alerts(
    db: Session, unit: CoalUnit, record: EfficiencyRecord, deviations: list[DeviationAnalysis]
) -> None:
    # 供电煤耗超标
    warn_line = unit.design_net_coal_rate + COAL_RATE_WARN_MARGIN
    crit_line = unit.design_net_coal_rate + COAL_RATE_CRIT_MARGIN
    if record.net_coal_rate > warn_line:
        is_crit = record.net_coal_rate > crit_line
        new_alert = not _has_open(db, unit.id, "COAL_RATE")
        raise_alert(
            db,
            unit_id=unit.id,
            category="COAL_RATE",
            level="CRITICAL" if is_crit else "WARNING",
            title=f"{unit.name} 供电煤耗偏高",
            measured_value=record.net_coal_rate,
            threshold_value=round(warn_line, 2),
            message=f"实测供电煤耗 {record.net_coal_rate} g/kWh，超设计目标 {unit.design_net_coal_rate}。",
        )
        if is_crit and new_alert:
            integration_client.push_event_to_safety(
                unit_code=unit.code,
                level="CRITICAL",
                title=f"{unit.name} 供电煤耗严重超标",
                detail=f"{record.net_coal_rate} g/kWh，超目标 {COAL_RATE_CRIT_MARGIN}+ g/kWh。",
            )

    # 锅炉效率偏低——常见诱因是空预器堵灰、漏风，转设备点检排查
    if record.boiler_eff < unit.design_boiler_eff - BOILER_EFF_MARGIN:
        new_alert = not _has_open(db, unit.id, "BOILER_EFF")
        raise_alert(
            db,
            unit_id=unit.id,
            category="BOILER_EFF",
            level="WARNING",
            title=f"{unit.name} 锅炉效率偏低",
            measured_value=record.boiler_eff,
            threshold_value=round(unit.design_boiler_eff - BOILER_EFF_MARGIN, 2),
            message=f"锅炉效率 {record.boiler_eff}%，低于设计 {unit.design_boiler_eff}%，排烟热损失 q2={record.q2}%。",
        )
        if new_alert:
            integration_client.push_defect_to_inspection(
                unit_code=unit.code,
                title=f"{unit.name} 锅炉效率下降疑似受热面/空预器问题",
                detail=f"锅炉效率 {record.boiler_eff}%，q2 排烟热损失 {record.q2}%，建议排查空预器堵灰/漏风。",
            )

    # 耗差合计超阈值
    total = round(sum(d.coal_rate_impact for d in deviations), 3)
    if total > TOTAL_DEVIATION_THRESHOLD:
        raise_alert(
            db,
            unit_id=unit.id,
            category="DEVIATION",
            level="WARNING",
            title=f"{unit.name} 运行耗差偏大",
            measured_value=total,
            threshold_value=TOTAL_DEVIATION_THRESHOLD,
            message=f"当前小指标耗差合计 {total} g/kWh，建议按耗差排序逐项治理。",
        )


def process_snapshot(
    db: Session, unit: CoalUnit, snap: OperatingSnapshot
) -> tuple[EfficiencyRecord, list[DeviationAnalysis]]:
    record = efficiency_engine.compute_record(unit, snap)
    db.add(record)
    db.commit()
    db.refresh(record)
    deviations = efficiency_engine.analyze_deviations(db, unit, snap, persist=True)
    _check_alerts(db, unit, record, deviations)
    return record, deviations
