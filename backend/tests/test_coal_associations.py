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


def test_invalid_storage_strings_and_unusable_unit_code_rejected(client, unit_factory, eng_headers):
    unit = unit_factory(code='U-01')
    spaced = unit_factory(code=' U-02 ')
    path = '/api/integration/coal-quality-allocations'
    for key in ('source_instance', 'batch_id', 'unit_code', 'evidence'):
        body = declaration(unit, unit_code='U-01')
        body[key] = 'bad\u0000value'
        response = client.post(path, json=body, headers=eng_headers)
        assert response.status_code == 422, (key, response.text)
    response = client.post(path, json=declaration(spaced), headers=eng_headers)
    assert response.status_code == 422


def test_unpaired_surrogates_are_rejected_with_serializable_errors(client, unit_factory, eng_headers):
    import json
    unit = unit_factory()
    path = '/api/integration/coal-quality-allocations'
    for key in ('source_instance', 'batch_id', 'unit_code', 'evidence'):
        body = declaration(unit)
        body[key] = '\ud800'
        body['valid_to'] = 'bogus'
        response = client.post(path, content=json.dumps(body), headers={**eng_headers, 'Content-Type': 'application/json'})
        assert response.status_code == 422
        assert response.json()['detail']
    body = declaration(unit)
    body['\ud800'] = {'nested': ['\ud800']}
    response = client.post(path, content=json.dumps(body), headers={**eng_headers, 'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['detail']


def test_concurrent_same_request_creates_one_record(client, unit_factory, eng_headers):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    unit = unit_factory()
    body = declaration(unit)
    start = Barrier(2)
    def send():
        start.wait(timeout=10)
        return client.post('/api/integration/coal-quality-allocations', json=body, headers=eng_headers)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: send(), range(2)))
    assert sorted(item.status_code for item in results) == [200, 201]
    assert results[0].json()['id'] == results[1].json()['id']


def test_concurrent_conflicting_request_preserves_one_declaration(client, unit_factory, eng_headers):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    unit = unit_factory()
    first = declaration(unit)
    second = dict(first, evidence='另一份模拟依据')
    start = Barrier(2)
    def send(body):
        start.wait(timeout=10)
        return client.post('/api/integration/coal-quality-allocations', json=body, headers=eng_headers)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(send, (first, second)))
    assert sorted(item.status_code for item in results) == [201, 409]
    winner = next(item.json() for item in results if item.status_code == 201)
    read = client.get(f"/api/integration/coal-quality-allocations/{winner['id']}", headers=eng_headers)
    assert read.json()['evidence'] == winner['evidence']
