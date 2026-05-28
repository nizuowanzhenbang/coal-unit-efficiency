"""能效记录查询与趋势测试。"""

from __future__ import annotations

from tests.conftest import make_snapshot_payload


def _seed_records(client, unit_id, headers, n=3):
    for i in range(n):
        client.post(
            "/api/snapshots",
            json=make_snapshot_payload(unit_id, load_mw=540 + i * 10),
            headers=headers,
        )


def test_list_efficiency_records(client, unit_factory, operator_headers, viewer_headers):
    unit = unit_factory()
    _seed_records(client, unit.id, operator_headers, 3)
    resp = client.get(f"/api/efficiency?unit_id={unit.id}", headers=viewer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_efficiency_trend_shape(client, unit_factory, operator_headers):
    unit = unit_factory()
    _seed_records(client, unit.id, operator_headers, 4)
    resp = client.get(f"/api/efficiency/trend/{unit.id}", headers=operator_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["ts"]) == 4
    assert len(body["net_coal_rate"]) == 4
    assert len(body["boiler_eff"]) == 4
    # 趋势按时间正序
    assert body["ts"] == sorted(body["ts"])


def test_efficiency_trend_empty(client, unit_factory, operator_headers):
    unit = unit_factory()
    resp = client.get(f"/api/efficiency/trend/{unit.id}", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json()["ts"] == []


def test_efficiency_requires_auth(client):
    assert client.get("/api/efficiency").status_code == 401
