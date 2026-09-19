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
    assert body['evaluation']['mode'] == 'PRIOR'
    assert body['evaluation']['valid_samples'] == 0  # 当前工况不得参与自身训练。
    assert body['evaluation']['snapshot_id'] > 0
    stored = client.get(f'/api/optimization?unit_id={unit.id}', headers=eng_headers).json()[0]
    assert stored['evaluation'] == body['evaluation']


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


def test_history_disabled_is_persisted_as_explicit_prior(client, unit_factory, operator_headers, eng_headers):
    unit = _prep(client, unit_factory, operator_headers)
    result = client.post('/api/optimization/generate', json={'unit_id': unit.id, 'use_history': False}, headers=eng_headers)
    assert result.status_code == 201
    assert result.json()['evaluation']['reason'] == 'HISTORY_DISABLED'
    assert result.json()['confidence'] == 0


def test_history_is_chronological_deduplicated_and_excludes_current(db, unit_factory):
    from datetime import datetime, timedelta, timezone
    from app.models.operation import OperatingSnapshot
    from app.routers.optimization import _history_samples
    from app.services.efficiency_engine import compute_record
    unit = unit_factory()
    cutoff = datetime(2026, 6, 2, tzinfo=timezone.utc)
    ids = []
    for hours in (3, 1, 2, 0, -1):
        snap = OperatingSnapshot(**make_snapshot_payload(unit.id), ts=cutoff - timedelta(hours=hours))
        db.add(snap)
        db.commit()
        ids.append(snap.id)
        db.add(compute_record(unit, snap))
        db.add(compute_record(unit, snap))  # 同一工况重复计算，不应变成两条训练样本。
        db.commit()
    rows = _history_samples(db, unit.id, cutoff)
    assert [row['snapshot_id'] for row in rows] == [ids[0], ids[2], ids[1]]


def test_existing_database_upgrade_preserves_legacy_evaluation_as_null():
    from sqlalchemy import create_engine
    from app.database import ensure_evaluation_column
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE optimization_suggestions (id INTEGER PRIMARY KEY, rationale TEXT)')
        conn.exec_driver_sql("INSERT INTO optimization_suggestions VALUES (1, 'legacy')")
    ensure_evaluation_column(engine)
    ensure_evaluation_column(engine)
    with engine.connect() as conn:
        assert tuple(conn.exec_driver_sql('SELECT rationale, evaluation FROM optimization_suggestions').one()) == ('legacy', None)
    engine.dispose()


def test_price_changes_do_not_rewrite_saved_calculation_inputs(client, unit_factory, operator_headers, eng_headers, monkeypatch):
    from app.config import settings
    unit = _prep(client, unit_factory, operator_headers)
    monkeypatch.setattr(settings, 'standard_coal_price', 900.0)
    first = client.post('/api/optimization/generate', json={'unit_id': unit.id}, headers=eng_headers).json()
    assert first['evaluation']['input_snapshot']['standard_coal_price'] == 900
    assert first['evaluation']['input_snapshot']['capacity_mw'] == 600
    monkeypatch.setattr(settings, 'standard_coal_price', 1100.0)
    second = client.post('/api/optimization/generate', json={'unit_id': unit.id}, headers=eng_headers).json()
    assert first['evaluation']['input_sha256'] != second['evaluation']['input_sha256']
    stored = client.get(f'/api/optimization?unit_id={unit.id}', headers=eng_headers).json()
    original = next(row for row in stored if row['id'] == first['id'])
    assert original['evaluation'] == first['evaluation']


def test_snapshot_offsets_cannot_reverse_history_order(client, unit_factory, operator_headers, eng_headers):
    unit = unit_factory()
    for stamp in ('2026-06-01T09:00:00+08:00', '2026-06-01T02:00:00Z'):
        assert client.post('/api/snapshots', json=make_snapshot_payload(unit.id, ts=stamp), headers=operator_headers).status_code == 201
    result = client.post('/api/optimization/generate', json={'unit_id': unit.id}, headers=eng_headers).json()
    assert result['evaluation']['snapshot_ts'].startswith('2026-06-01T02:00:00')
    assert result['evaluation']['history_end'].startswith('2026-06-01T01:00:00')
