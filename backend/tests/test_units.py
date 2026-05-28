"""机组台账路由测试。"""

from __future__ import annotations


def _unit_payload(code="U-09", **kw):
    payload = dict(code=code, name="测试机组", capacity_mw=600.0, design_net_coal_rate=300.0)
    payload.update(kw)
    return payload


def test_create_unit(client, eng_headers):
    resp = client.post("/api/units", json=_unit_payload(), headers=eng_headers)
    assert resp.status_code == 201
    assert resp.json()["code"] == "U-09"


def test_create_unit_duplicate(client, eng_headers):
    client.post("/api/units", json=_unit_payload("U-10"), headers=eng_headers)
    dup = client.post("/api/units", json=_unit_payload("U-10"), headers=eng_headers)
    assert dup.status_code == 409


def test_create_unit_forbidden_for_operator(client, operator_headers):
    resp = client.post("/api/units", json=_unit_payload("U-11"), headers=operator_headers)
    assert resp.status_code == 403


def test_list_units(client, eng_headers, viewer_headers):
    client.post("/api/units", json=_unit_payload("U-12"), headers=eng_headers)
    resp = client.get("/api/units", headers=viewer_headers)
    assert resp.status_code == 200
    assert any(u["code"] == "U-12" for u in resp.json())


def test_get_unit_not_found(client, viewer_headers):
    assert client.get("/api/units/9999", headers=viewer_headers).status_code == 404


def test_update_unit(client, eng_headers):
    created = client.post("/api/units", json=_unit_payload("U-13"), headers=eng_headers).json()
    resp = client.patch(
        f"/api/units/{created['id']}", json={"design_net_coal_rate": 295.0}, headers=eng_headers
    )
    assert resp.status_code == 200
    assert resp.json()["design_net_coal_rate"] == 295.0


def test_list_active_only(client, eng_headers):
    created = client.post("/api/units", json=_unit_payload("U-14"), headers=eng_headers).json()
    client.patch(f"/api/units/{created['id']}", json={"is_active": False}, headers=eng_headers)
    active = client.get("/api/units?active_only=true", headers=eng_headers).json()
    assert all(u["code"] != "U-14" for u in active)
