"""锅炉反平衡效率算法测试。"""

from __future__ import annotations

import pytest

from app.algorithms import boiler_efficiency as be


def test_excess_air_ratio_basic():
    assert be.excess_air_ratio(0.0) == pytest.approx(1.0, abs=1e-6)
    assert be.excess_air_ratio(3.0) == pytest.approx(21 / 18, abs=1e-6)
    # 越高的含氧量 → 越大的过量空气系数
    assert be.excess_air_ratio(5.0) > be.excess_air_ratio(3.0)


def test_excess_air_ratio_clamped():
    # 极端含氧量不应导致除零/负值
    assert be.excess_air_ratio(25.0) > 0


def test_q2_increases_with_flue_temp():
    low = be.q2_flue_gas_loss(120, 20, 1.2)
    high = be.q2_flue_gas_loss(150, 20, 1.2)
    assert high > low > 0


def test_q2_increases_with_excess_air():
    assert be.q2_flue_gas_loss(130, 20, 1.4) > be.q2_flue_gas_loss(130, 20, 1.1)


def test_q2_zero_when_no_temp_diff():
    assert be.q2_flue_gas_loss(20, 20, 1.2) == 0.0


def test_q4_increases_with_fly_ash_carbon():
    low = be.q4_unburned_carbon_loss(15, 20000, 2.0, 5.0)
    high = be.q4_unburned_carbon_loss(15, 20000, 5.0, 5.0)
    assert high > low > 0


def test_q4_zero_lhv_guarded():
    assert be.q4_unburned_carbon_loss(15, 0, 3, 5) == 0.0


def test_q5_drops_with_load():
    full = be.q5_radiation_loss(600, 600)
    half = be.q5_radiation_loss(300, 600)
    # 低负荷时散热占比抬升
    assert half > full > 0


def test_q6_positive():
    assert be.q6_ash_physical_loss(15, 20000) > 0


def test_boiler_efficiency_realistic_range():
    res = be.boiler_efficiency(
        flue_gas_temp=125,
        ambient_temp=20,
        flue_o2=3.6,
        ash_ar=15,
        coal_lhv=21000,
        fly_ash_carbon=2.5,
        slag_carbon=5.0,
        load_mw=560,
        capacity_mw=600,
    )
    assert 88.0 < res.efficiency < 96.0
    # 各项损失之和 = 100 - 效率
    total = res.q2 + res.q3 + res.q4 + res.q5 + res.q6
    assert res.efficiency == pytest.approx(100 - total, abs=1e-3)


def test_boiler_efficiency_degraded_lower():
    good = be.boiler_efficiency(
        flue_gas_temp=120, ambient_temp=20, flue_o2=3.2, ash_ar=14, coal_lhv=22000,
        fly_ash_carbon=1.8, slag_carbon=4.0, load_mw=640, capacity_mw=660,
    )
    bad = be.boiler_efficiency(
        flue_gas_temp=150, ambient_temp=20, flue_o2=5.5, ash_ar=18, coal_lhv=19500,
        fly_ash_carbon=4.5, slag_carbon=6.0, load_mw=540, capacity_mw=600,
    )
    assert good.efficiency > bad.efficiency
