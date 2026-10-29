from copy import deepcopy
from uuid import uuid4
import pytest
from app.models.operation import OperatingSnapshot
from tests.test_coal_associations import declaration
from tests.test_coal_quality_preview import payload

PATH = '/api/integration/coal-quality-measurements'

def evidence(unit):
    return {'request_id': str(uuid4()), 'measurement': payload(unit)['measurement'],
            'time_provenance': {'kind': 'caller_declared_offset', 'offset_minutes': 480,
                                'stored_time': '2026-10-28T08:00:00', 'evidence': '合成实验室 UTC+08'}}

def test_save_read_replay_conflict_and_roles(client, db, unit_factory, eng_headers, viewer_headers, operator_headers):
    body = evidence(unit_factory())
    assert client.post(PATH, json=body).status_code == 401
    assert client.post(PATH, json=body, headers=viewer_headers).status_code == 403
    first = client.post(PATH, json=body, headers=eng_headers)
    assert first.status_code == 201, first.text
    saved = first.json()
    assert saved['measurement'] == body['measurement']
    assert saved['time_provenance'] == body['time_provenance']
    assert len(saved['content_sha256']) == 64
    assert saved['created_by'] == 'u_energy_eng'
    repeated = client.post(PATH, json=body, headers=eng_headers)
    assert repeated.status_code == 200 and repeated.json() == saved
    assert client.post(PATH, json=body, headers=operator_headers).status_code == 409
    changed = deepcopy(body)
    changed['time_provenance']['evidence'] = '新说明'
    assert client.post(PATH, json=changed, headers=eng_headers).status_code == 409
    changed['request_id'] = str(uuid4())
    revision = client.post(PATH, json=changed, headers=eng_headers)
    assert revision.status_code == 201
    assert revision.json()['content_sha256'] != saved['content_sha256']
    db.expire_all()
    assert client.get(f"{PATH}/{saved['id']}", headers=viewer_headers).json() == saved
    assert client.get(f"{PATH}/999999", headers=eng_headers).status_code == 404
    assert db.query(OperatingSnapshot).count() == 0

@pytest.mark.parametrize('key,value', [('offset_minutes', 0), ('offset_minutes', True),
    ('offset_minutes', 841), ('stored_time', '2026-10-28T00:00:00'),
    ('stored_time', '2026-10-28T08:00:00+08:00'), ('stored_time', 'bad'),
    ('evidence', ' '), ('evidence', 'a\x00b'), ('kind', 'verified')])
def test_invalid_provenance(client, unit_factory, eng_headers, key, value):
    body = evidence(unit_factory())
    body['time_provenance'][key] = value
    assert client.post(PATH, json=body, headers=eng_headers).status_code == 422

@pytest.mark.parametrize('key', ['source_instance', 'batch_id', 'test_id'])
def test_invalid_nested_storage_text(client, unit_factory, eng_headers, key):
    body = evidence(unit_factory())
    body['measurement'][key] = 'bad\x00text'
    assert client.post(PATH, json=body, headers=eng_headers).status_code == 422

def test_evidenced_preview(client, db, unit_factory, eng_headers):
    unit = unit_factory()
    saved = client.post(PATH, json=evidence(unit), headers=eng_headers)
    assert saved.status_code == 201, saved.text
    allocation = client.post('/api/integration/coal-quality-allocations', json=declaration(unit), headers=eng_headers).json()
    request = {'measurement_id': saved.json()['id'], 'allocation_id': allocation['id'], 'conditions': payload(unit)['conditions']}
    preview_path = '/api/integration/coal-quality-preview/evidenced'
    result = client.post(preview_path, json=request, headers=eng_headers)
    assert result.status_code == 200, result.text
    assert result.json()['coal_lhv_kj_kg'] == 16747.2
    assert result.json()['measurement_evidence'] == saved.json()
    wrong = client.post('/api/integration/coal-quality-allocations', json=declaration(unit, source_instance='other'), headers=eng_headers).json()
    assert client.post(preview_path, json={**request, 'allocation_id': wrong['id']}, headers=eng_headers).status_code == 422
    assert client.post(preview_path, json={**request, 'measurement_id': 999999}, headers=eng_headers).status_code == 404
    assert db.query(OperatingSnapshot).count() == 0

def test_concurrent_evidence_replay(client, unit_factory, eng_headers):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    body = evidence(unit_factory())
    barrier = Barrier(2)
    def send(_):
        barrier.wait(timeout=10)
        return client.post(PATH, json=body, headers=eng_headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    assert sorted(r.status_code for r in results) == [200, 201]
    assert results[0].json() == results[1].json()
