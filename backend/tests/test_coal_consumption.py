"""煤耗与效率换算算法测试。"""

from __future__ import annotations

import pytest

from app.algorithms import coal_consumption as cc


def test_ideal_coal_rate_constant():
    # 100% 效率下 1 kWh 理论耗标煤约 122.84 g
    assert cc.IDEAL_COAL_RATE == pytest.approx(122.84, abs=0.1)


def test_standard_coal_flow_scales_with_lhv():
    # 实际煤热值高于标煤 → 折标煤量大于实物量
    std = cc.standard_coal_flow_tph(100, 35000)
    assert std > 100
    std_low = cc.standard_coal_flow_tph(100, 20000)
    assert std_low < 100


def test_gross_coal_rate_measured():
    rate = cc.gross_coal_rate_measured(coal_flow_tph=240, coal_lhv=21000, gross_power_mw=560)
    # 量级应在 250~320 g/kWh
    assert 250 < rate < 330


def test_gross_coal_rate_zero_power():
    assert cc.gross_coal_rate_measured(240, 21000, 0) == 0.0


def test_net_coal_rate_higher_than_gross():
    gross = 290.0
    net = cc.net_coal_rate(gross, aux_ratio_pct=5.0)
    assert net > gross
    assert net == pytest.approx(gross / 0.95, abs=1e-6)


def test_net_coal_rate_guard():
    assert cc.net_coal_rate(290, 100) == 0.0


def test_gross_efficiency_product():
    eff = cc.gross_efficiency(93.0, 99.0, 45.0)
    assert eff == pytest.approx(93 * 99 * 45 / 10000, abs=1e-6)
    assert 35 < eff < 50


def test_coal_rate_from_eff_matches_measured_roughly():
    rate = cc.gross_coal_rate_from_eff(93.0, 99.0, 45.0)
    assert 280 < rate < 320


def test_heat_rate_from_eff():
    hr = cc.heat_rate_from_eff(41.4)
    assert hr == pytest.approx(3600 / 0.414, abs=1.0)


def test_coal_saving_sign():
    # 实际低于目标 → 节约为正
    saving = cc.coal_saving_t(actual_rate=290, target_rate=300, gen_mwh=14000)
    assert saving > 0
    over = cc.coal_saving_t(actual_rate=310, target_rate=300, gen_mwh=14000)
    assert over < 0


def test_cost_and_co2():
    saving_t = 100.0
    assert cc.cost_saving_yuan(saving_t, 850) == 85000.0
    assert cc.co2_reduction_t(saving_t, 2.66) == 266.0
