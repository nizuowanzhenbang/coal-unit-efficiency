"""耗差分析算法测试。"""

from __future__ import annotations

from app.algorithms import deviation as dv


def test_lower_better_positive_when_above_target():
    # 排烟温度越低越好：高于目标 → 多烧（正）
    impact = dv.coal_rate_impact(140, 125, sensitivity=0.22, direction=dv.LOWER_BETTER)
    assert impact > 0


def test_lower_better_negative_when_below_target():
    impact = dv.coal_rate_impact(118, 125, sensitivity=0.22, direction=dv.LOWER_BETTER)
    assert impact < 0


def test_higher_better_positive_when_below_target():
    # 主蒸汽温度越高越好：低于目标 → 多烧（正）
    impact = dv.coal_rate_impact(530, 538, sensitivity=0.13, direction=dv.HIGHER_BETTER)
    assert impact > 0


def test_classify_severity_levels():
    assert dv.classify_severity(0.1) == "NORMAL"
    assert dv.classify_severity(1.0) == "WATCH"
    assert dv.classify_severity(3.0) == "ALERT"


def test_analyze_indicator_uses_default_meta():
    res = dv.analyze_indicator("flue_gas_temp", 140, 125)
    assert res.label == "排烟温度"
    assert res.unit == "℃"
    assert res.coal_rate_impact > 0
    assert res.severity in {"NORMAL", "WATCH", "ALERT"}


def test_analyze_indicator_custom_sensitivity():
    res = dv.analyze_indicator(
        "custom", 10, 5, sensitivity=2.0, direction=dv.LOWER_BETTER, label="自定义", unit="x"
    )
    assert res.coal_rate_impact == 10.0
    assert res.label == "自定义"


def test_total_impact_sums():
    results = [
        dv.analyze_indicator("flue_gas_temp", 140, 125),
        dv.analyze_indicator("flue_o2", 5.0, 3.5),
    ]
    total = dv.total_impact(results)
    assert total == round(sum(r.coal_rate_impact for r in results), 3)
    assert total > 0


def test_default_sensitivities_cover_key_indicators():
    for key in ("flue_gas_temp", "flue_o2", "fly_ash_carbon", "condenser_vacuum", "aux_ratio"):
        assert key in dv.DEFAULT_SENSITIVITIES
