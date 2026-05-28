"""工况录入 → 能效计算 → 耗差/告警联动测试。"""

from __future__ import annotations

from app.models.alert import Alert
from app.models.analysis import BenchmarkTarget, DeviationAnalysis
from app.models.user import Role
from tests.conftest import make_snapshot_payload


def _add_benchmarks(db, unit_id):
    from app.algorithms.deviation import DEFAULT_SENSITIVITIES

    targets = {
        "flue_gas_temp": 125.0,
        "flue_o2": 3.5,
        "fly_ash_carbon": 2.5,
        "condenser_vacuum": 4.8,
        "aux_ratio": 5.5,
    }
    for ind, tgt in targets.items():
        meta = DEFAULT_SENSITIVITIES[ind]
        db.add(BenchmarkTarget(unit_id=unit_id, indicator=ind, label=meta["label"],
                               unit_text=meta["unit"], target_value=tgt, sensitivity=meta["sens"],
                               direction=meta["direction"]))
    db.commit()


def test_create_snapshot_returns_efficiency(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    resp = client.post("/api/snapshots", json=make_snapshot_payload(unit.id), headers=operator_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["net_coal_rate"] > 0
    assert body["boiler_eff"] > 0
    assert body["net_coal_rate"] >= body["gross_coal_rate"]


def test_create_snapshot_unknown_unit(client, operator_headers):
    resp = client.post("/api/snapshots", json=make_snapshot_payload(9999), headers=operator_headers)
    assert resp.status_code == 404


def test_snapshot_forbidden_for_viewer(client, unit_factory, viewer_headers):
    unit = unit_factory()
    resp = client.post("/api/snapshots", json=make_snapshot_payload(unit.id), headers=viewer_headers)
    assert resp.status_code == 403


def test_snapshot_creates_deviations(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    _add_benchmarks(db, unit.id)
    client.post(
        "/api/snapshots",
        json=make_snapshot_payload(unit.id, flue_gas_temp=150, flue_o2=5.5),
        headers=operator_headers,
    )
    devs = db.query(DeviationAnalysis).filter(DeviationAnalysis.unit_id == unit.id).all()
    assert len(devs) >= 4
    flue = next(d for d in devs if d.indicator == "flue_gas_temp")
    assert flue.coal_rate_impact > 0


def test_high_coal_rate_raises_alert(client, db, unit_factory, operator_headers):
    unit = unit_factory(design_net_coal_rate=290.0)
    # 高煤量 + 差工况 → 供电煤耗远超设计 → 告警
    client.post(
        "/api/snapshots",
        json=make_snapshot_payload(unit.id, coal_flow_tph=300, flue_gas_temp=155, flue_o2=6.0,
                                   fly_ash_carbon=5.0, coal_lhv=19000),
        headers=operator_headers,
    )
    alerts = db.query(Alert).filter(Alert.unit_id == unit.id, Alert.category == "COAL_RATE").all()
    assert len(alerts) == 1


def test_alert_dedup(client, db, unit_factory, operator_headers):
    unit = unit_factory(design_net_coal_rate=290.0)
    payload = make_snapshot_payload(unit.id, coal_flow_tph=300, flue_gas_temp=155, flue_o2=6.0, coal_lhv=19000)
    client.post("/api/snapshots", json=payload, headers=operator_headers)
    client.post("/api/snapshots", json=payload, headers=operator_headers)
    alerts = db.query(Alert).filter(Alert.unit_id == unit.id, Alert.category == "COAL_RATE").all()
    # 同类未关闭告警只保留一条
    assert len(alerts) == 1


def test_latest_snapshot(client, unit_factory, operator_headers):
    unit = unit_factory()
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id, load_mw=500), headers=operator_headers)
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id, load_mw=580), headers=operator_headers)
    resp = client.get(f"/api/snapshots/latest/{unit.id}", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json()["load_mw"] == 580


def test_latest_snapshot_none(client, unit_factory, operator_headers):
    unit = unit_factory()
    assert client.get(f"/api/snapshots/latest/{unit.id}", headers=operator_headers).status_code == 404
