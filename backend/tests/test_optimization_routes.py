"""AI 燃烧优化路由测试。"""

from __future__ import annotations

from tests.conftest import make_snapshot_payload


def _prep(client, unit_factory, operator_headers):
    unit = unit_factory(capacity_mw=600.0)
    client.post(
        "/api/snapshots",
        json=make_snapshot_payload(unit.id, load_mw=560, flue_o2=5.2, flue_gas_temp=145, fly_ash_carbon=4.0),
        headers=operator_headers,
    )
    return unit


def test_generate_suggestion(client, unit_factory, operator_headers, eng_headers):
    unit = _prep(client, unit_factory, operator_headers)
    resp = client.post("/api/optimization/generate", json={"unit_id": unit.id}, headers=eng_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["recommended_o2"] < body["current_o2"]
    assert body["predicted_coal_rate_drop"] > 0
    assert body["code"].startswith("OPT-")
    assert body["status"] == "PENDING"


def test_generate_no_snapshot(client, unit_factory, eng_headers):
    unit = unit_factory()
    resp = client.post("/api/optimization/generate", json={"unit_id": unit.id}, headers=eng_headers)
    assert resp.status_code == 400


def test_generate_forbidden_operator(client, unit_factory, operator_headers):
    unit = _prep(client, unit_factory, operator_headers)
    resp = client.post("/api/optimization/generate", json={"unit_id": unit.id}, headers=operator_headers)
    assert resp.status_code == 403


def test_list_and_update_status(client, unit_factory, operator_headers, eng_headers):
    unit = _prep(client, unit_factory, operator_headers)
    created = client.post("/api/optimization/generate", json={"unit_id": unit.id}, headers=eng_headers).json()
    listing = client.get(f"/api/optimization?unit_id={unit.id}", headers=eng_headers).json()
    assert len(listing) == 1
    upd = client.patch(f"/api/optimization/{created['id']}", json={"status": "ADOPTED"}, headers=eng_headers)
    assert upd.status_code == 200
    assert upd.json()["status"] == "ADOPTED"


def test_update_invalid_status(client, unit_factory, operator_headers, eng_headers):
    unit = _prep(client, unit_factory, operator_headers)
    created = client.post("/api/optimization/generate", json={"unit_id": unit.id}, headers=eng_headers).json()
    resp = client.patch(f"/api/optimization/{created['id']}", json={"status": "BOGUS"}, headers=eng_headers)
    assert resp.status_code == 422
