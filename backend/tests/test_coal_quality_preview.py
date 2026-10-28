"""显式煤批次关联与实际能效计算；所有数据均为合成场景。"""
from copy import deepcopy

import pytest

from app.models.operation import OperatingSnapshot
from tests.conftest import make_snapshot_payload


def payload(unit):
    conditions = make_snapshot_payload(unit.id)
    conditions.pop('unit_id')
    conditions.pop('coal_lhv')
    conditions['ts'] = '2026-10-28T01:00:00+00:00'
    return {
        'contract_version': 'coal-quality-energy/v1',
        'measurement': {
            'source_system': 'coal-quality-monitor', 'source_instance': 'plant-a',
            'batch_id': '1', 'test_id': '7', 'metric': 'Qnet', 'basis': 'ar',
            'unit': 'kcal/kg', 'value': 4000, 'measured_at': '2026-10-28T08:00:00+08:00',
        },
        'allocation': {
            'source_instance': 'plant-a', 'batch_id': '1', 'unit_code': unit.code,
            'valid_from': '2026-10-28T00:00:00Z', 'valid_to': '2026-10-29T00:00:00Z',
        },
        'conditions': conditions,
    }


def test_preview_converts_and_uses_real_engine_without_writing(client, db, unit_factory, eng_headers):
    unit = unit_factory()
    body = payload(unit)
    response = client.post('/api/integration/coal-quality-preview', json=body, headers=eng_headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['coal_lhv_kj_kg'] == 16747.2
    assert result['lineage']['measurement'] == body['measurement']
    assert result['lineage']['measured_at_utc'] == '2026-10-28T00:00:00Z'
    assert result['lineage']['measurement_age_seconds'] == 3600
    assert result['lineage']['conversion_factor'] == '4.1868'
    assert result['mode'] == 'scenario_preview'
    assert db.query(OperatingSnapshot).count() == 0
    actual = client.post('/api/snapshots', headers=eng_headers, json={
        **body['conditions'], 'unit_id': unit.id, 'coal_lhv': 16747.2,
    })
    assert actual.status_code == 201
    assert result['efficiency']['net_coal_rate'] == actual.json()['net_coal_rate']
    second = deepcopy(body)
    second['measurement'].update(unit='kJ/kg', value=16747.2)
    equivalent = client.post('/api/integration/coal-quality-preview', json=second, headers=eng_headers)
    assert equivalent.status_code == 200
    assert equivalent.json()['efficiency'] == result['efficiency']


@pytest.mark.parametrize('section,key,value', [
    ('measurement', 'source_instance', 'plant-b'), ('measurement', 'batch_id', '2'),
    ('measurement', 'source_system', 'another-system'), ('measurement', 'test_id', ' '),
    ('measurement', 'metric', 'Qgr'), ('measurement', 'basis', 'd'),
    ('measurement', 'unit', 'MJ/kg'), ('measurement', 'value', 0),
    ('measurement', 'value', 'NaN'), ('measurement', 'value', 'Infinity'),
    ('measurement', 'value', 10001), ('measurement', 'value', True),
    ('measurement', 'measured_at', '2026-10-28T00:00:00'),
    ('measurement', 'measured_at', '2026-10-28T02:00:00Z'),
    ('allocation', 'valid_to', '2026-10-28T01:00:00Z'),
    ('allocation', 'valid_from', '2026-10-28T02:00:00Z'),
    ('conditions', 'load_mw', 0), ('conditions', 'aux_power_mw', 999),
    ('conditions', 'coal_flow_tph', 'NaN'), ('conditions', 'ts', '2026-10-28T01:00:00'),
])
def test_invalid_contract_is_rejected(client, unit_factory, eng_headers, section, key, value):
    body = payload(unit_factory())
    body[section][key] = value
    response = client.post('/api/integration/coal-quality-preview', json=body, headers=eng_headers)
    assert response.status_code == 422, response.text


def test_target_and_roles_and_unknown_fields(client, unit_factory, eng_headers, viewer_headers):
    body = payload(unit_factory())
    assert client.post('/api/integration/coal-quality-preview', json=body).status_code == 401
    assert client.post('/api/integration/coal-quality-preview', json=body, headers=viewer_headers).status_code == 403
    body['allocation']['unit_code'] = 'MISSING'
    assert client.post('/api/integration/coal-quality-preview', json=body, headers=eng_headers).status_code == 404
    body['unexpected'] = 'not ignored'
    assert client.post('/api/integration/coal-quality-preview', json=body, headers=eng_headers).status_code == 422


@pytest.mark.parametrize('section,key,value', [
    (section, key, value)
    for section, key in [('measurement', 'measured_at'), ('allocation', 'valid_from'),
                         ('allocation', 'valid_to'), ('conditions', 'ts')]
    for value in ['0001-01-01T00:00:00+08:00', '9999-12-31T23:59:59-08:00']
])
def test_unrepresentable_utc_is_rejected(client, unit_factory, eng_headers, section, key, value):
    body = payload(unit_factory())
    body[section][key] = value
    response = client.post('/api/integration/coal-quality-preview', json=body, headers=eng_headers)
    assert response.status_code == 422


def test_normal_cross_day_offset_remains_valid(client, unit_factory, eng_headers):
    body = payload(unit_factory())
    body['measurement']['measured_at'] = '2026-10-27T20:00:00-04:00'
    response = client.post('/api/integration/coal-quality-preview', json=body, headers=eng_headers)
    assert response.status_code == 200
    assert response.json()['lineage']['measured_at_utc'] == '2026-10-28T00:00:00Z'
