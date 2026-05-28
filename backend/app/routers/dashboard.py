"""能效驾驶舱：机组群实时能效画像聚合。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models.alert import Alert
from ..models.analysis import OptimizationSuggestion
from ..models.operation import EfficiencyRecord
from ..models.unit import CoalUnit
from ..models.user import User

router = APIRouter(prefix="/dashboard", tags=["能效驾驶舱"])


def _latest_record(db: Session, unit_id: int) -> EfficiencyRecord | None:
    return (
        db.query(EfficiencyRecord)
        .filter(EfficiencyRecord.unit_id == unit_id)
        .order_by(EfficiencyRecord.ts.desc())
        .first()
    )


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    units = db.query(CoalUnit).filter(CoalUnit.is_active.is_(True)).order_by(CoalUnit.code).all()

    cards = []
    rate_sum = 0.0
    rate_n = 0
    total_load = 0.0
    for u in units:
        rec = _latest_record(db, u.id)
        if rec is None:
            cards.append(
                {
                    "unit_id": u.id,
                    "code": u.code,
                    "name": u.name,
                    "capacity_mw": u.capacity_mw,
                    "status": "NO_DATA",
                }
            )
            continue
        deviation = round(rec.net_coal_rate - u.design_net_coal_rate, 2)
        status = "GOOD" if deviation <= 0 else ("WATCH" if deviation <= 5 else "BAD")
        rate_sum += rec.net_coal_rate
        rate_n += 1
        total_load += rec.load_mw
        cards.append(
            {
                "unit_id": u.id,
                "code": u.code,
                "name": u.name,
                "capacity_mw": u.capacity_mw,
                "load_mw": rec.load_mw,
                "net_coal_rate": rec.net_coal_rate,
                "design_net_coal_rate": u.design_net_coal_rate,
                "deviation": deviation,
                "boiler_eff": rec.boiler_eff,
                "heat_rate": rec.heat_rate,
                "aux_ratio": rec.aux_ratio,
                "ts": rec.ts.isoformat(),
                "status": status,
            }
        )

    open_alerts = db.query(Alert).filter(Alert.status == "OPEN").count()
    crit_alerts = (
        db.query(Alert).filter(Alert.status == "OPEN", Alert.level == "CRITICAL").count()
    )
    pending_opt = (
        db.query(OptimizationSuggestion)
        .filter(OptimizationSuggestion.status == "PENDING")
        .count()
    )
    adopted_saving = (
        db.query(OptimizationSuggestion)
        .filter(OptimizationSuggestion.status == "ADOPTED")
        .all()
    )
    saving_yuan_day = round(sum(s.predicted_saving_yuan_day for s in adopted_saving), 2)

    return {
        "fleet": {
            "unit_count": len(units),
            "total_load_mw": round(total_load, 1),
            "avg_net_coal_rate": round(rate_sum / rate_n, 2) if rate_n else 0.0,
            "open_alerts": open_alerts,
            "critical_alerts": crit_alerts,
            "pending_optimizations": pending_opt,
            "adopted_saving_yuan_day": saving_yuan_day,
        },
        "units": cards,
    }
