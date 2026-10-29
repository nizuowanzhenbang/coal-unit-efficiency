"""验证时间声明与化验快照的内部一致性，不认证外部来源。"""
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID
import hashlib
import json
from pydantic import Field, StrictInt, field_validator, model_validator
from .coal_quality_adapter import ContractModel, Measurement

class TimeProvenance(ContractModel):
    kind: Literal['caller_declared_offset']
    offset_minutes: Annotated[StrictInt, Field(ge=-840, le=840)]
    stored_time: Annotated[str, Field(min_length=1, max_length=40)]
    evidence: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator('evidence')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('时间依据不能为空')
        return value

class MeasurementCreate(ContractModel):
    request_id: UUID
    measurement: Measurement
    time_provenance: TimeProvenance

    @model_validator(mode='after')
    def coherent(self):
        for value in [self.measurement.source_instance, self.measurement.batch_id,
                      self.measurement.test_id, self.time_provenance.evidence]:
            if '\x00' in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise ValueError('文本包含不可存储字符')
        p, m = self.time_provenance, self.measurement
        stored = datetime.fromisoformat(p.stored_time)
        if stored.tzinfo is not None:
            raise ValueError('stored_time必须是不带时区的原始钟面时间')
        if (m.measured_at.utcoffset() != timedelta(minutes=p.offset_minutes)
                or m.measured_at.replace(tzinfo=None) != stored):
            raise ValueError('时区声明与化验时间不一致')
        return self

    def content(self):
        data = {'contract_version': 'coal-quality-energy/v1',
                'measurement': self.measurement.model_dump(mode='json'),
                'time_provenance': self.time_provenance.model_dump(mode='json')}
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        return encoded, hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def evidence_dict(row):
    return {'id': row.id, 'request_id': row.request_id, 'kind': 'operator_submitted',
            **json.loads(row.content_json), 'content_sha256': row.content_sha256,
            'created_by': row.created_by, 'created_at': row.created_at}
