"""AI 燃烧寻优算法测试。"""

from __future__ import annotations

from app.algorithms.combustion_optimizer import (
    CombustionOptimizer,
    optimal_o2_for_load,
    optimize_combustion,
)


def test_optimal_o2_decreases_with_load():
    low = optimal_o2_for_load(300, 600)
    high = optimal_o2_for_load(600, 600)
    assert low > high
    assert 2.5 <= high <= 5.0


def test_recommend_without_history_uses_prior():
    opt = CombustionOptimizer()
    res = opt.recommend(
        load_mw=560, capacity_mw=600, current_o2=5.2, current_flue_temp=145, current_fly_ash_carbon=4.0
    )
    assert not opt.fitted
    assert res.confidence == 0.6
    # 当前氧量高于最优 → 有正向节煤空间
    assert res.predicted_coal_rate_drop > 0
    assert res.recommended_o2 < 5.2
    assert res.model_version


def test_recommend_no_drop_when_already_optimal():
    opt = CombustionOptimizer()
    rec_o2 = optimal_o2_for_load(560, 600)
    res = opt.recommend(
        load_mw=560, capacity_mw=600, current_o2=rec_o2, current_flue_temp=120, current_fly_ash_carbon=2.0
    )
    assert res.predicted_coal_rate_drop == 0.0


def test_fit_marks_fitted_with_enough_samples():
    samples = [
        {"load_mw": 500 + i * 5, "flue_o2": 3.0 + i * 0.1, "flue_gas_temp": 120 + i,
         "fly_ash_carbon": 2.0 + i * 0.05, "net_coal_rate": 290 + i * 0.8}
        for i in range(20)
    ]
    opt = CombustionOptimizer().fit(samples)
    assert opt.fitted
    pred = opt.predict_coal_rate(560, 4.0, 130, 3.0)
    assert pred is not None


def test_fit_skipped_with_few_samples():
    opt = CombustionOptimizer().fit([{"load_mw": 1, "flue_o2": 1, "flue_gas_temp": 1,
                                      "fly_ash_carbon": 1, "net_coal_rate": 1}])
    assert not opt.fitted
    assert opt.predict_coal_rate(1, 1, 1, 1) is None


def test_optimize_combustion_helper():
    res = optimize_combustion(
        load_mw=560, capacity_mw=600, current_o2=5.0, current_flue_temp=140, current_fly_ash_carbon=4.0
    )
    assert res.recommended_o2 > 0
    assert res.secondary_air
    assert res.mill_combo


def test_high_fly_ash_adds_drop():
    opt = CombustionOptimizer()
    rec_o2 = optimal_o2_for_load(560, 600)
    clean = opt.recommend(load_mw=560, capacity_mw=600, current_o2=rec_o2,
                          current_flue_temp=120, current_fly_ash_carbon=2.0)
    dirty = opt.recommend(load_mw=560, capacity_mw=600, current_o2=rec_o2,
                          current_flue_temp=120, current_fly_ash_carbon=6.0)
    assert dirty.predicted_coal_rate_drop > clean.predicted_coal_rate_drop
