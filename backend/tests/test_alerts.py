"""能效预警路由测试。"""

from __future__ import annotations

from app.services.alerting import raise_alert
from tests.conftest import make_snapshot_payload


def _raise(db, unit_id, category="COAL_RATE", level="WARNING"):
    return raise_alert(db, unit_id=unit_id, category=category, level=level, title="t",
                       measured_value=310, threshold_value=305, message="m")


def test_list_alerts(client, db, unit_factory, viewer_headers):
    unit = unit_factory()
    _raise(db, unit.id)
    resp = client.get(f"/api/alerts?unit_id={unit.id}", headers=viewer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_filter_by_status(client, db, unit_factory, viewer_headers):
    unit = unit_factory()
    _raise(db, unit.id)
    open_list = client.get("/api/alerts?status_filter=OPEN", headers=viewer_headers).json()
    closed_list = client.get("/api/alerts?status_filter=CLOSED", headers=viewer_headers).json()
    assert len(open_list) == 1
    assert len(closed_list) == 0


def test_ack_then_close(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    alert = _raise(db, unit.id)
    acked = client.patch(f"/api/alerts/{alert.id}", json={"status": "ACKED"}, headers=operator_headers)
    assert acked.json()["status"] == "ACKED"
    closed = client.patch(f"/api/alerts/{alert.id}", json={"status": "CLOSED"}, headers=operator_headers)
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"] is not None


def test_update_invalid_status(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    alert = _raise(db, unit.id)
    resp = client.patch(f"/api/alerts/{alert.id}", json={"status": "X"}, headers=operator_headers)
    assert resp.status_code == 422


def test_alert_dedup_refreshes(client, db, unit_factory):
    unit = unit_factory()
    a1 = _raise(db, unit.id)
    a2 = _raise(db, unit.id, level="CRITICAL")
    # 同机组同类未关闭 → 复用同一条
    assert a1.id == a2.id
    assert a2.level == "CRITICAL"


def test_full_snapshot_alert_listed(client, db, unit_factory, operator_headers, viewer_headers):
    unit = unit_factory(design_net_coal_rate=290.0)
    client.post("/api/snapshots",
                json=make_snapshot_payload(unit.id, coal_flow_tph=305, flue_gas_temp=158, coal_lhv=19000),
                headers=operator_headers)
    resp = client.get(f"/api/alerts?unit_id={unit.id}", headers=viewer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
