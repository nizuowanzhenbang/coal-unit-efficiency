"""对标基准路由测试。"""

from __future__ import annotations


def _bench(unit_id, indicator="flue_gas_temp", **kw):
    payload = dict(unit_id=unit_id, indicator=indicator, label="排烟温度", unit_text="℃",
                   target_value=125.0, sensitivity=0.22, direction="LOWER_BETTER")
    payload.update(kw)
    return payload


def test_create_benchmark(client, unit_factory, eng_headers):
    unit = unit_factory()
    resp = client.post("/api/benchmarks", json=_bench(unit.id), headers=eng_headers)
    assert resp.status_code == 201
    assert resp.json()["indicator"] == "flue_gas_temp"


def test_upsert_overwrites(client, unit_factory, eng_headers):
    unit = unit_factory()
    client.post("/api/benchmarks", json=_bench(unit.id, target_value=125.0), headers=eng_headers)
    again = client.post("/api/benchmarks", json=_bench(unit.id, target_value=120.0), headers=eng_headers)
    assert again.status_code == 201
    assert again.json()["target_value"] == 120.0
    listing = client.get(f"/api/benchmarks?unit_id={unit.id}", headers=eng_headers).json()
    assert len(listing) == 1


def test_benchmark_forbidden_for_operator(client, unit_factory, operator_headers):
    unit = unit_factory()
    resp = client.post("/api/benchmarks", json=_bench(unit.id), headers=operator_headers)
    assert resp.status_code == 403


def test_update_benchmark(client, unit_factory, eng_headers):
    unit = unit_factory()
    created = client.post("/api/benchmarks", json=_bench(unit.id), headers=eng_headers).json()
    resp = client.patch(f"/api/benchmarks/{created['id']}", json={"sensitivity": 0.3}, headers=eng_headers)
    assert resp.status_code == 200
    assert resp.json()["sensitivity"] == 0.3


def test_delete_benchmark(client, unit_factory, eng_headers):
    unit = unit_factory()
    created = client.post("/api/benchmarks", json=_bench(unit.id), headers=eng_headers).json()
    assert client.delete(f"/api/benchmarks/{created['id']}", headers=eng_headers).status_code == 200
    listing = client.get(f"/api/benchmarks?unit_id={unit.id}", headers=eng_headers).json()
    assert listing == []
