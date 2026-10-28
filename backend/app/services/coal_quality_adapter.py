"""显式煤质来源与机组关联，仅用于情景能效预览，不写运行账本。"""
from datetime import datetime, timezone
from decimal import Decimal
from math import isfinite
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def numeric_input(value):
    if isinstance(value, bool):
        raise ValueError('数值不能为布尔值')
    if isinstance(value, float) and not isfinite(value):
        return str(value)
    return value


Number = Annotated[float, BeforeValidator(numeric_input), Field(allow_inf_nan=False)]
Identity = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^\S(?:.*\S)?$')]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Measurement(ContractModel):
    source_system: Literal['coal-quality-monitor']
    source_instance: Identity
    batch_id: Identity
    test_id: Identity
    metric: Literal['Qnet']
    basis: Literal['ar']
    unit: Literal['kcal/kg', 'kJ/kg']
    value: Annotated[Number, Field(gt=0, le=41868)]
    measured_at: AwareDatetime

    @model_validator(mode='after')
    def heat_range(self):
        if self.unit == 'kcal/kg' and self.value > 10000:
            raise ValueError('热值超出煤质契约范围')
        return self


class Allocation(ContractModel):
    source_instance: Identity
    batch_id: Identity
    unit_code: Identity
    valid_from: AwareDatetime
    valid_to: AwareDatetime


class Conditions(ContractModel):
    ts: AwareDatetime
    load_mw: Annotated[Number, Field(ge=1, le=2000)]
    main_steam_temp: Annotated[Number, Field(ge=0, le=1000)]
    main_steam_press: Annotated[Number, Field(gt=0, le=100)]
    reheat_steam_temp: Annotated[Number, Field(ge=0, le=1000)]
    feedwater_temp: Annotated[Number, Field(ge=0, le=500)]
    flue_gas_temp: Annotated[Number, Field(ge=0, le=1000)]
    flue_o2: Annotated[Number, Field(ge=0, le=20.5)]
    fly_ash_carbon: Annotated[Number, Field(ge=0, le=99)]
    slag_carbon: Annotated[Number, Field(ge=0, le=99)] = 5
    condenser_vacuum: Annotated[Number, Field(gt=0, le=100)]
    ambient_temp: Annotated[Number, Field(ge=-100, le=100)] = 20
    coal_flow_tph: Annotated[Number, Field(gt=0, le=10000)]
    aux_power_mw: Annotated[Number, Field(ge=0, le=2000)]


class CoalQualityPreview(ContractModel):
    contract_version: Literal['coal-quality-energy/v1']
    measurement: Measurement
    allocation: Allocation
    conditions: Conditions

    @model_validator(mode='after')
    def association(self):
        m, a, c = self.measurement, self.allocation, self.conditions
        if (m.source_instance, m.batch_id) != (a.source_instance, a.batch_id):
            raise ValueError('来源实例或批次与显式关联不一致')
        if not a.valid_from <= c.ts < a.valid_to:
            raise ValueError('工况时间必须在关联窗口内（左闭右开）')
        if m.measured_at > c.ts:
            raise ValueError('不能使用工况发生后才取得的化验')
        if c.aux_power_mw >= c.load_mw:
            raise ValueError('厂用电必须小于负荷')
        return self


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def adapt(payload: CoalQualityPreview) -> tuple[float, dict]:
    m = payload.measurement
    factor = Decimal('4.1868') if m.unit == 'kcal/kg' else Decimal('1')
    value = float(Decimal(str(m.value)) * factor)
    return value, {
        'contract_version': payload.contract_version,
        'measurement': m.model_dump(mode='json'),
        'allocation': payload.allocation.model_dump(mode='json'),
        'measured_at_utc': utc_text(m.measured_at),
        'snapshot_at_utc': utc_text(payload.conditions.ts),
        'measurement_age_seconds': (payload.conditions.ts - m.measured_at).total_seconds(),
        'conversion_factor': str(factor),
        'target_metric': 'coal_lhv', 'target_basis': 'ar', 'target_unit': 'kJ/kg',
        'association_method': 'explicit_scenario_allocation',
    }
