"""耗差分析路由测试。"""

from __future__ import annotations

from app.models.analysis import BenchmarkTarget
from tests.conftest import make_snapshot_payload


def _add_bench(db, unit_id):
    from app.algorithms.deviation import DEFAULT_SENSITIVITIES

    for ind, tgt in {"flue_gas_temp": 125.0, "flue_o2": 3.5}.items():
        meta = DEFAULT_SENSITIVITIES[ind]
        db.add(BenchmarkTarget(unit_id=unit_id, indicator=ind, label=meta["label"],
                               unit_text=meta["unit"], target_value=tgt, sensitivity=meta["sens"],
                               direction=meta["direction"]))
    db.commit()


def test_analyze_now(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    _add_bench(db, unit.id)
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id, flue_gas_temp=148),
                headers=operator_headers)
    resp = client.post(f"/api/deviations/analyze/{unit.id}", headers=operator_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert any(d["indicator"] == "flue_gas_temp" for d in body)


def test_analyze_no_snapshot(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    _add_bench(db, unit.id)
    resp = client.post(f"/api/deviations/analyze/{unit.id}", headers=operator_headers)
    assert resp.status_code == 400


def test_analyze_unknown_unit(client, operator_headers):
    assert client.post("/api/deviations/analyze/9999", headers=operator_headers).status_code == 404


def test_list_deviations(client, db, unit_factory, operator_headers):
    unit = unit_factory()
    _add_bench(db, unit.id)
    client.post("/api/snapshots", json=make_snapshot_payload(unit.id), headers=operator_headers)
    resp = client.get(f"/api/deviations?unit_id={unit.id}", headers=operator_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2
