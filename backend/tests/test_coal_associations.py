"""情景关联不是实际入炉记录；使用合成数据验证持久身份与预览。"""
from copy import deepcopy
from uuid import uuid4

from app.models.operation import OperatingSnapshot
from tests.test_coal_quality_preview import payload


def declaration(unit, **updates):
    value = {'request_id': str(uuid4()), 'source_instance': 'plant-a', 'batch_id': '1',
             'unit_code': unit.code, 'valid_from': '2026-10-28T08:00:00+08:00',
             'valid_to': '2026-10-29T08:00:00+08:00', 'evidence': '人工指定的模拟情景'}
    value.update(updates)
    return value


def test_create_read_idempotency_and_conflict(client, db, unit_factory, eng_headers, viewer_headers):
    unit = unit_factory()
    body = declaration(unit)
    path = '/api/integration/coal-quality-allocations'
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers=viewer_headers).status_code == 403
    first = client.post(path, json=body, headers=eng_headers)
    assert first.status_code == 201, first.text
    saved = first.json()
    assert saved['kind'] == 'scenario' and saved['created_by']
    assert saved['valid_from'] == '2026-10-28T00:00:00Z'
    assert saved['evidence'] == body['evidence']
    repeated = client.post(path, json=body, headers=eng_headers)
    assert repeated.status_code == 200 and repeated.json() == saved
    changed = dict(body, evidence='其他依据')
    assert client.post(path, json=changed, headers=eng_headers).status_code == 409
    db.expire_all()
    assert client.get(f"{path}/{saved['id']}", headers=viewer_headers).json() == saved
    second = declaration(unit, source_instance='plant-b')
    different = client.post(path, json=second, headers=eng_headers)
    assert different.status_code == 201 and different.json()['id'] != saved['id']
    assert db.query(OperatingSnapshot).count() == 0


def test_saved_association_drives_real_preview_and_rejects_mismatch(client, db, unit_factory, eng_headers):
    unit = unit_factory()
    response = client.post('/api/integration/coal-quality-allocations', json=declaration(unit), headers=eng_headers)
    assert response.status_code == 201, response.text
    saved = response.json()
    original = payload(unit)
    body = {'allocation_id': saved['id'], 'measurement': original['measurement'], 'conditions': original['conditions']}
    path = '/api/integration/coal-quality-preview/saved'
    preview = client.post(path, json=body, headers=eng_headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()['coal_lhv_kj_kg'] == 16747.2
    assert preview.json()['association_id'] == saved['id']
    for key, value in [('source_instance', 'plant-b'), ('batch_id', '2')]:
        invalid = deepcopy(body)
        invalid['measurement'][key] = value
        assert client.post(path, json=invalid, headers=eng_headers).status_code == 422
    assert client.post(path, json={**body, 'allocation_id': 999999}, headers=eng_headers).status_code == 404
    assert db.query(OperatingSnapshot).count() == 0


def test_invalid_association_is_rejected(client, unit_factory, eng_headers):
    unit = unit_factory()
    path = '/api/integration/coal-quality-allocations'
    for update, code in [({'unit_code': 'missing'}, 404), ({'evidence': '  '}, 422),
                         ({'valid_to': '2026-10-28T00:00:00Z'}, 422),
                         ({'valid_from': '2026-10-28T00:00:00'}, 422),
                         ({'request_id': 'not-a-uuid'}, 422)]:
        assert client.post(path, json=declaration(unit, **update), headers=eng_headers).status_code == code


def test_invalid_nonfinite_json_and_huge_identifier_return_422(client, unit_factory, eng_headers):
    unit = unit_factory()
    body = declaration(unit)
    import json
    body['unexpected'] = {'nested': [float('inf')]}
    response = client.post('/api/integration/coal-quality-allocations', content=json.dumps(body),
                           headers={**eng_headers, 'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert client.get('/api/integration/coal-quality-allocations/9999999999999999999999999',
                      headers=eng_headers).status_code == 422
