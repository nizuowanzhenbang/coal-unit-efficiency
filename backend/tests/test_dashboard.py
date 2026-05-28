"""能效驾驶舱聚合测试。"""

from __future__ import annotations

from tests.conftest import make_snapshot_payload


def test_overview_empty(client, viewer_headers):
    resp = client.get("/api/dashboard/overview", headers=viewer_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["fleet"]["unit_count"] == 0
    assert body["units"] == []


def test_overview_with_units(client, unit_factory, operator_headers, viewer_headers):
    u1 = unit_factory(design_net_coal_rate=300.0)
    u2 = unit_factory(design_net_coal_rate=290.0)
    client.post("/api/snapshots", json=make_snapshot_payload(u1.id), headers=operator_headers)
    client.post("/api/snapshots", json=make_snapshot_payload(u2.id), headers=operator_headers)
    body = client.get("/api/dashboard/overview", headers=viewer_headers).json()
    assert body["fleet"]["unit_count"] == 2
    assert body["fleet"]["avg_net_coal_rate"] > 0
    assert len(body["units"]) == 2
    for card in body["units"]:
        assert card["status"] in {"GOOD", "WATCH", "BAD", "NO_DATA"}


def test_overview_no_data_unit(client, unit_factory, viewer_headers):
    unit_factory()
    body = client.get("/api/dashboard/overview", headers=viewer_headers).json()
    assert body["units"][0]["status"] == "NO_DATA"


def test_overview_requires_auth(client):
    assert client.get("/api/dashboard/overview").status_code == 401
