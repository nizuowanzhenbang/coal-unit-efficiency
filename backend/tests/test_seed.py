"""种子数据完整性测试。"""

from __future__ import annotations

from app.models.alert import Alert
from app.models.analysis import OptimizationSuggestion
from app.models.operation import EfficiencyRecord, OperatingSnapshot
from app.models.report import EnergyReport
from app.models.unit import CoalUnit
from app.models.user import User
from app.seed_data import seed


def test_seed_populates_full_demo(db):
    seed(db)
    assert db.query(User).count() == 5
    assert db.query(CoalUnit).count() == 3
    # 3 台机组 × 24h 工况
    assert db.query(OperatingSnapshot).count() == 72
    assert db.query(EfficiencyRecord).count() == 72
    assert db.query(OptimizationSuggestion).count() == 3
    assert db.query(EnergyReport).count() == 3


def test_seed_u01_triggers_alert(db):
    seed(db)
    u01 = db.query(CoalUnit).filter(CoalUnit.code == "U-01").first()
    alerts = db.query(Alert).filter(Alert.unit_id == u01.id).all()
    assert len(alerts) >= 1


def test_seed_u03_efficient(db):
    seed(db)
    u03 = db.query(CoalUnit).filter(CoalUnit.code == "U-03").first()
    rec = (
        db.query(EfficiencyRecord)
        .filter(EfficiencyRecord.unit_id == u03.id)
        .order_by(EfficiencyRecord.ts.desc())
        .first()
    )
    # 超超临界机组供电煤耗应明显低于亚临界
    assert rec.net_coal_rate < 290
