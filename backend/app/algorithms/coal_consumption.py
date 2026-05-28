"""煤耗与效率换算。

供电煤耗（g/kWh）是火电厂能效的"总分"：发出（送出）1 度电烧掉多少克标准煤。
标准煤定义为低位发热量 29307 kJ/kg，实际煤按热值折算成标煤后再算。
理想极限：1 kWh = 3600 kJ，全部转成电需 3600/29307 kg ≈ 122.84 g 标煤，
真实煤耗 = 122.84 / 总效率。
"""

from __future__ import annotations

STD_COAL_LHV = 29307.0
IDEAL_COAL_RATE = 3600.0 / STD_COAL_LHV * 1000.0  # g/kWh，约 122.84


def standard_coal_flow_tph(coal_flow_tph: float, coal_lhv: float, std_lhv: float = STD_COAL_LHV) -> float:
    """实际煤量按热值折算成标准煤量 t/h。"""
    return coal_flow_tph * coal_lhv / std_lhv


def gross_coal_rate_measured(
    coal_flow_tph: float, coal_lhv: float, gross_power_mw: float, std_lhv: float = STD_COAL_LHV
) -> float:
    """实测发电煤耗 g/kWh = 标煤量(g/h) / 发电量(kWh/h)。"""
    if gross_power_mw <= 0:
        return 0.0
    std_gph = standard_coal_flow_tph(coal_flow_tph, coal_lhv, std_lhv) * 1_000_000.0
    return std_gph / (gross_power_mw * 1000.0)


def net_coal_rate(gross_coal_rate: float, aux_ratio_pct: float) -> float:
    """供电煤耗 = 发电煤耗 / (1 − 厂用电率)。厂用电先在自家烧掉一部分。"""
    denom = 1.0 - aux_ratio_pct / 100.0
    if denom <= 0:
        return 0.0
    return gross_coal_rate / denom


def gross_efficiency(boiler_eff_pct: float, pipe_eff_pct: float, turbine_eff_pct: float) -> float:
    """发电效率 % = 锅炉效率 × 管道效率 × 汽机循环效率（三者均为百分数）。"""
    return boiler_eff_pct * pipe_eff_pct * turbine_eff_pct / 10000.0


def gross_coal_rate_from_eff(
    boiler_eff_pct: float, pipe_eff_pct: float, turbine_eff_pct: float
) -> float:
    """反平衡法发电煤耗 g/kWh = 122.84 / 总效率。"""
    eff = gross_efficiency(boiler_eff_pct, pipe_eff_pct, turbine_eff_pct) / 100.0
    if eff <= 0:
        return 0.0
    return IDEAL_COAL_RATE / eff


def heat_rate_from_eff(gross_eff_pct: float) -> float:
    """机组热耗率 kJ/kWh = 3600 / 发电效率。"""
    if gross_eff_pct <= 0:
        return 0.0
    return 3600.0 / (gross_eff_pct / 100.0)


def coal_saving_t(actual_rate: float, target_rate: float, gen_mwh: float) -> float:
    """较目标节约的标煤量 t（正=省、负=超）。"""
    gen_kwh = gen_mwh * 1000.0
    return (target_rate - actual_rate) * gen_kwh / 1_000_000.0


def cost_saving_yuan(saving_t: float, price_per_t: float) -> float:
    return saving_t * price_per_t


def co2_reduction_t(saving_t: float, co2_factor: float) -> float:
    return saving_t * co2_factor
