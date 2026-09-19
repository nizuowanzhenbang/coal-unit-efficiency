"""Pydantic 出入参模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- 认证 / 用户 ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str = ""
    role: str = "VIEWER"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class UserOut(_ORM):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


# ---- 机组 ----
class UnitBase(BaseModel):
    code: str
    name: str
    capacity_mw: float
    boiler_model: str = ""
    turbine_model: str = ""
    design_net_coal_rate: float = 300.0
    design_boiler_eff: float = 93.0
    design_pipe_eff: float = 99.0
    design_turbine_eff: float = 45.0
    design_heat_rate: float = 7800.0
    design_aux_ratio: float = 5.5
    design_ash_ar: float = 15.0
    design_coal_lhv: float = 20900.0
    commission_date: date | None = None


class UnitCreate(UnitBase):
    pass


class UnitUpdate(BaseModel):
    name: str | None = None
    capacity_mw: float | None = None
    boiler_model: str | None = None
    turbine_model: str | None = None
    design_net_coal_rate: float | None = None
    design_boiler_eff: float | None = None
    design_pipe_eff: float | None = None
    design_turbine_eff: float | None = None
    design_heat_rate: float | None = None
    design_aux_ratio: float | None = None
    design_ash_ar: float | None = None
    design_coal_lhv: float | None = None
    is_active: bool | None = None


class UnitOut(_ORM):
    id: int
    code: str
    name: str
    capacity_mw: float
    boiler_model: str
    turbine_model: str
    design_net_coal_rate: float
    design_boiler_eff: float
    design_pipe_eff: float
    design_turbine_eff: float
    design_heat_rate: float
    design_aux_ratio: float
    design_ash_ar: float
    design_coal_lhv: float
    commission_date: date | None
    is_active: bool


# ---- 工况快照 ----
class SnapshotCreate(BaseModel):
    unit_id: int
    load_mw: float
    main_steam_temp: float
    main_steam_press: float
    reheat_steam_temp: float
    feedwater_temp: float
    flue_gas_temp: float
    flue_o2: float
    fly_ash_carbon: float
    slag_carbon: float = 5.0
    condenser_vacuum: float
    ambient_temp: float = 20.0
    coal_flow_tph: float
    coal_lhv: float
    aux_power_mw: float
    ts: datetime | None = None


class SnapshotOut(_ORM):
    id: int
    unit_id: int
    ts: datetime
    load_mw: float
    main_steam_temp: float
    main_steam_press: float
    reheat_steam_temp: float
    feedwater_temp: float
    flue_gas_temp: float
    flue_o2: float
    fly_ash_carbon: float
    slag_carbon: float
    condenser_vacuum: float
    ambient_temp: float
    coal_flow_tph: float
    coal_lhv: float
    aux_power_mw: float


# ---- 能效记录 ----
class EfficiencyOut(_ORM):
    id: int
    unit_id: int
    ts: datetime
    load_mw: float
    gross_coal_rate: float
    net_coal_rate: float
    boiler_eff: float
    pipe_eff: float
    turbine_eff: float
    gross_eff: float
    net_eff: float
    heat_rate: float
    aux_ratio: float
    excess_air: float
    q2: float
    q3: float
    q4: float
    q5: float
    q6: float


# ---- 对标基准 ----
class BenchmarkCreate(BaseModel):
    unit_id: int
    indicator: str
    label: str = ""
    unit_text: str = ""
    target_value: float
    design_value: float = 0.0
    sensitivity: float = 0.0
    direction: str = "LOWER_BETTER"


class BenchmarkUpdate(BaseModel):
    label: str | None = None
    unit_text: str | None = None
    target_value: float | None = None
    design_value: float | None = None
    sensitivity: float | None = None
    direction: str | None = None


class BenchmarkOut(_ORM):
    id: int
    unit_id: int
    indicator: str
    label: str
    unit_text: str
    target_value: float
    design_value: float
    sensitivity: float
    direction: str
    updated_at: datetime


# ---- 耗差 ----
class DeviationOut(_ORM):
    id: int
    unit_id: int
    ts: datetime
    indicator: str
    label: str
    actual_value: float
    target_value: float
    deviation: float
    coal_rate_impact: float
    severity: str


# ---- AI 优化建议 ----
class OptimizeRequest(BaseModel):
    unit_id: int
    use_history: bool = True


class OptimizationOut(_ORM):
    id: int
    unit_id: int
    code: str
    ts: datetime
    load_mw: float
    coal_lhv: float
    current_o2: float
    recommended_o2: float
    current_flue_temp: float
    current_fly_ash_carbon: float
    recommended_secondary_air: str
    recommended_mill_combo: str
    predicted_coal_rate_drop: float
    predicted_saving_yuan_day: float
    confidence: float
    model_version: str
    rationale: str
    evaluation: dict | None = None
    status: str


class OptimizationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(PENDING|ADOPTED|REJECTED)$")


# ---- 报告 ----
class ReportGenerateRequest(BaseModel):
    unit_id: int
    period_type: str = "DAILY"
    period_start: datetime
    period_end: datetime
    target_rate: float | None = None


class ReportOut(_ORM):
    id: int
    unit_id: int
    code: str
    period_type: str
    period_start: datetime
    period_end: datetime
    avg_net_coal_rate: float
    target_net_coal_rate: float
    coal_rate_deviation: float
    avg_boiler_eff: float
    avg_heat_rate: float
    avg_aux_ratio: float
    total_gen_mwh: float
    coal_saving_t: float
    cost_saving_yuan: float
    co2_reduction_t: float
    top_deviations: str
    summary: str
    status: str
    created_at: datetime


# ---- 告警 ----
class AlertOut(_ORM):
    id: int
    unit_id: int
    code: str
    category: str
    level: str
    title: str
    measured_value: float
    threshold_value: float
    message: str
    status: str
    triggered_at: datetime
    closed_at: datetime | None


class AlertStatusUpdate(BaseModel):
    status: str = Field(pattern="^(OPEN|ACKED|CLOSED)$")
