"""能效报告路由测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import make_snapshot_payload


def _window():
    now = datetime.now(timezone.utc)
    return (now - timedelta(hours=2)).isoformat(), now.isoformat()


def _gen_payload(unit_id, **kw):
    start, end = _window()
    payload = dict(unit_id=unit_id, period_type="DAILY", period_start=start, period_end=end)
    payload.update(kw)
    return payload


def test_generate_report(client, unit_factory, operator_headers, eng_headers):
    unit = unit_factory(design_net_coal_rate=300.0)
    for i in range(3):
        client.post("/api/snapshots", json=make_snapshot_payload(unit.id, load_mw=550 + i),
                    headers=operator_headers)
    resp = client.post("/api/reports/generate", json=_gen_payload(unit.id), headers=eng_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"].startswith("ER-")
    assert body["avg_net_coal_rate"] > 0
    assert body["status"] == "DRAFT"
    assert "供电煤耗" in body["summary"]


def test_generate_report_unknown_unit(client, eng_headers):
    resp = client.post("/api/reports/generate", json=_gen_payload(9999), headers=eng_headers)
    assert resp.status_code == 404


def test_report_forbidden_operator(client, unit_factory, operator_headers):
    unit = unit_factory()
    resp = client.post("/api/reports/generate", json=_gen_payload(unit.id), headers=operator_headers)
    assert resp.status_code == 403


def test_issue_report(client, unit_factory, operator_headers, eng_headers):
    unit = unit_factory()
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id), headers=operator_headers)
    created = client.post("/api/reports/generate", json=_gen_payload(unit.id), headers=eng_headers).json()
    resp = client.post(f"/api/reports/{created['id']}/issue", headers=eng_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ISSUED"


def test_list_reports(client, unit_factory, operator_headers, eng_headers, viewer_headers):
    unit = unit_factory()
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id), headers=operator_headers)
    client.post("/api/reports/generate", json=_gen_payload(unit.id), headers=eng_headers)
    resp = client.get(f"/api/reports?unit_id={unit.id}", headers=viewer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_savings_positive_when_below_target(client, unit_factory, operator_headers, eng_headers):
    unit = unit_factory(design_net_coal_rate=320.0)
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id), headers=operator_headers)
    # 目标设很高 → 实际优于目标 → 节约为正
    created = client.post("/api/reports/generate", json=_gen_payload(unit.id, target_rate=340.0),
                          headers=eng_headers).json()
    assert created["coal_saving_t"] > 0
    assert created["cost_saving_yuan"] > 0
    assert created["co2_reduction_t"] > 0
