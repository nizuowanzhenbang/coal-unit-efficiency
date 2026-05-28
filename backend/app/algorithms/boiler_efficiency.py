"""锅炉效率反平衡法（热损失法）。

正平衡要准确计量入炉燃料量，现场误差大；反平衡只需测烟气/灰渣等参数，
把"跑掉的热"逐项算出来，效率 = 100% − Σ各项热损失。参照 GB 10184 / DL/T 904。

各项损失：
    q2 排烟热损失   —— 烟气带着热从烟囱跑了，排烟温度越高、空气过量越多越大
    q3 化学不完全燃烧 —— 烟气里残留 CO 等可燃气体
    q4 机械不完全燃烧 —— 飞灰、炉渣里没烧尽的碳
    q5 散热损失     —— 炉墙向外散热，绝对值近似恒定，低负荷时占比抬高
    q6 灰渣物理热损失 —— 高温炉渣带走的显热
"""

from __future__ import annotations

from dataclasses import dataclass

CARBON_LHV = 32700.0  # 碳的发热量 kJ/kg


@dataclass(slots=True)
class BoilerEfficiencyResult:
    excess_air: float
    q2: float
    q3: float
    q4: float
    q5: float
    q6: float
    efficiency: float


def excess_air_ratio(flue_o2: float) -> float:
    """过量空气系数 α = 21 / (21 − O₂)（干基烟气含氧量法）。"""
    o2 = min(max(flue_o2, 0.0), 20.5)
    return 21.0 / (21.0 - o2)


def q2_flue_gas_loss(flue_gas_temp: float, ambient_temp: float, excess_air: float) -> float:
    """排烟热损失 %：随排烟温度与过量空气系数单调上升。"""
    delta = max(flue_gas_temp - ambient_temp, 0.0)
    return (3.5 + 0.5 * excess_air) * delta / 100.0


def q4_unburned_carbon_loss(
    ash_ar: float,
    coal_lhv: float,
    fly_ash_carbon: float,
    slag_carbon: float,
    fly_share: float = 0.9,
    slag_share: float = 0.1,
) -> float:
    """机械不完全燃烧损失 %：灰渣里没烧尽的碳折成热量占比。"""
    if coal_lhv <= 0:
        return 0.0
    fly_c = min(max(fly_ash_carbon, 0.0), 99.0)
    slag_c = min(max(slag_carbon, 0.0), 99.0)
    term = fly_share * fly_c / (100.0 - fly_c) + slag_share * slag_c / (100.0 - slag_c)
    return (CARBON_LHV / coal_lhv) * ash_ar * term


def q5_radiation_loss(load_mw: float, capacity_mw: float, q5_rated: float = 0.3) -> float:
    """散热损失 %：绝对散热量近似恒定，占比随负荷下降而抬升。"""
    load = max(load_mw, 1.0)
    return q5_rated * capacity_mw / load


def q6_ash_physical_loss(
    ash_ar: float,
    coal_lhv: float,
    slag_share: float = 0.1,
    slag_temp: float = 800.0,
    ash_cp: float = 0.96,
) -> float:
    """灰渣物理热损失 %：炉渣带走的显热。"""
    if coal_lhv <= 0:
        return 0.0
    return slag_share * (ash_ar / 100.0) * ash_cp * slag_temp / coal_lhv * 100.0


def boiler_efficiency(
    *,
    flue_gas_temp: float,
    ambient_temp: float,
    flue_o2: float,
    ash_ar: float,
    coal_lhv: float,
    fly_ash_carbon: float,
    slag_carbon: float,
    load_mw: float,
    capacity_mw: float,
    q3: float = 0.1,
) -> BoilerEfficiencyResult:
    alpha = excess_air_ratio(flue_o2)
    q2 = q2_flue_gas_loss(flue_gas_temp, ambient_temp, alpha)
    q4 = q4_unburned_carbon_loss(ash_ar, coal_lhv, fly_ash_carbon, slag_carbon)
    q5 = q5_radiation_loss(load_mw, capacity_mw)
    q6 = q6_ash_physical_loss(ash_ar, coal_lhv)
    eff = 100.0 - (q2 + q3 + q4 + q5 + q6)
    return BoilerEfficiencyResult(
        excess_air=round(alpha, 4),
        q2=round(q2, 4),
        q3=round(q3, 4),
        q4=round(q4, 4),
        q5=round(q5, 4),
        q6=round(q6, 4),
        efficiency=round(eff, 4),
    )
