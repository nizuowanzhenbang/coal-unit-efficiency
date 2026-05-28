"""能效报告生成：把周期内的能效记录与耗差汇总成可汇报的日报/月报。"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from ..algorithms import coal_consumption as cc
from ..config import settings
from ..models.analysis import DeviationAnalysis
from ..models.operation import EfficiencyRecord
from ..models.report import EnergyReport
from ..models.unit import CoalUnit
from .codes import next_code


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def generate_report(
    db: Session,
    unit: CoalUnit,
    *,
    period_type: str,
    period_start: datetime,
    period_end: datetime,
    target_rate: float | None = None,
) -> EnergyReport:
    records = (
        db.query(EfficiencyRecord)
        .filter(
            EfficiencyRecord.unit_id == unit.id,
            EfficiencyRecord.ts >= period_start,
            EfficiencyRecord.ts <= period_end,
        )
        .all()
    )
    avg_net = round(_avg([r.net_coal_rate for r in records]), 3)
    avg_boiler = round(_avg([r.boiler_eff for r in records]), 3)
    avg_hr = round(_avg([r.heat_rate for r in records]), 1)
    avg_aux = round(_avg([r.aux_ratio for r in records]), 3)
    avg_load = _avg([r.load_mw for r in records])

    hours = max((period_end - period_start).total_seconds() / 3600.0, 0.0)
    gen_mwh = round(avg_load * hours, 2)

    target = target_rate if target_rate is not None else unit.design_net_coal_rate
    deviation = round(avg_net - target, 3) if avg_net else 0.0

    saving_t = round(cc.coal_saving_t(avg_net, target, gen_mwh), 3) if avg_net else 0.0
    cost_saving = round(cc.cost_saving_yuan(saving_t, settings.standard_coal_price), 2)
    co2_red = round(cc.co2_reduction_t(saving_t, settings.co2_factor), 3)

    # 主要耗差项：周期内按指标累计折算煤耗影响，取绝对值最大的前 5 项
    devs = (
        db.query(DeviationAnalysis)
        .filter(
            DeviationAnalysis.unit_id == unit.id,
            DeviationAnalysis.ts >= period_start,
            DeviationAnalysis.ts <= period_end,
        )
        .all()
    )
    agg: dict[str, dict] = defaultdict(lambda: {"label": "", "impact": 0.0, "count": 0})
    for d in devs:
        item = agg[d.indicator]
        item["label"] = d.label
        item["impact"] += d.coal_rate_impact
        item["count"] += 1
    top = sorted(
        (
            {"indicator": k, "label": v["label"], "avg_impact": round(v["impact"] / v["count"], 3)}
            for k, v in agg.items()
            if v["count"]
        ),
        key=lambda x: abs(x["avg_impact"]),
        reverse=True,
    )[:5]

    verdict = "优于目标" if deviation < 0 else "高于目标"
    summary = (
        f"{unit.name} 本期平均供电煤耗 {avg_net} g/kWh，{verdict} {abs(deviation)} g/kWh；"
        f"锅炉效率 {avg_boiler}%，厂用电率 {avg_aux}%；"
        f"较目标{'节约' if saving_t >= 0 else '多耗'}标煤 {abs(saving_t)} t，"
        f"折合金额 {abs(cost_saving)} 元，减碳 {abs(co2_red)} t。"
    )

    report = EnergyReport(
        unit_id=unit.id,
        code=next_code(db, EnergyReport, EnergyReport.code, "ER", date_fmt="%Y%m"),
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        avg_net_coal_rate=avg_net,
        target_net_coal_rate=round(target, 3),
        coal_rate_deviation=deviation,
        avg_boiler_eff=avg_boiler,
        avg_heat_rate=avg_hr,
        avg_aux_ratio=avg_aux,
        total_gen_mwh=gen_mwh,
        coal_saving_t=saving_t,
        cost_saving_yuan=cost_saving,
        co2_reduction_t=co2_red,
        top_deviations=json.dumps(top, ensure_ascii=False),
        summary=summary,
        status="DRAFT",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
