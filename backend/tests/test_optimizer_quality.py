"""模型必须在未参与拟合的样本上优于基线，否则明确降级。"""
import numpy as np
import pytest
from app.algorithms.combustion_optimizer import CombustionOptimizer


def good_samples(n=60):
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(n):
        load, o2, temp, fly = rng.uniform([450, 2.5, 110, 1], [590, 6, 160, 6])
        rows.append(dict(load_mw=load, flue_o2=o2, flue_gas_temp=temp, fly_ash_carbon=fly,
                         net_coal_rate=200 + .08 * load + 1.5 * o2 + .4 * temp + .8 * fly))
    return rows


def recommend(opt, **kwargs):
    return opt.recommend(**dict(load_mw=550, capacity_mw=600, current_o2=4,
                                current_flue_temp=135, current_fly_ash_carbon=3, **kwargs))


def test_reliable_history_reports_holdout_metrics_and_reproducible_dataset():
    result = recommend(CombustionOptimizer().fit(good_samples()))
    assert result.evaluation['mode'] == 'REGRESSION'
    assert result.evaluation['train_samples'] == 48
    assert result.evaluation['validation_samples'] == 12
    assert result.evaluation['validation_mae'] < 1e-6
    assert result.evaluation['baseline_mae'] > 0.1
    repeat = recommend(CombustionOptimizer().fit(good_samples()))
    assert result.evaluation['dataset_sha256'] == repeat.evaluation['dataset_sha256']


def test_future_regime_change_fails_validation_and_uses_prior():
    rows = good_samples()
    for row in rows[48:]:
        row['net_coal_rate'] += 80
    opt = CombustionOptimizer().fit(rows)
    assert not opt.fitted
    result = recommend(opt)
    assert result.model_version.startswith('combustion-prior-')
    assert result.evaluation['reason'] == 'VALIDATION_FAILED'


def test_rank_deficient_history_cannot_be_presented_as_validated_model():
    opt = CombustionOptimizer().fit([good_samples()[0]] * 30)
    assert not opt.fitted
    assert recommend(opt).evaluation['reason'] == 'RANK_DEFICIENT'


def test_refit_with_too_few_samples_discards_previous_model():
    opt = CombustionOptimizer().fit(good_samples())
    assert opt.fitted
    opt.fit(good_samples(2))
    assert not opt.fitted
    assert opt.predict_coal_rate(550, 4, 135, 3) is None


def test_malformed_and_nonfinite_history_is_excluded_and_counted():
    rows = good_samples() + [{}, {'net_coal_rate': 300}, {**good_samples()[0], 'flue_o2': float('nan')}]
    opt = CombustionOptimizer().fit(rows)
    assert opt.fitted
    evidence = recommend(opt).evaluation
    assert evidence['valid_samples'] == 60
    assert evidence['rejected_samples'] == 3


def test_extrapolation_is_explicitly_downgraded():
    opt = CombustionOptimizer().fit(good_samples())
    result = opt.recommend(load_mw=300, capacity_mw=600, current_o2=4,
                           current_flue_temp=135, current_fly_ash_carbon=3)
    assert result.evaluation['mode'] == 'PRIOR'
    assert result.evaluation['reason'] == 'OUTSIDE_TRAINING_RANGE'
    assert result.model_version.startswith('combustion-prior-')
    assert result.confidence == 0


@pytest.mark.parametrize('field,value', [('load_mw', 0), ('capacity_mw', -1), ('current_o2', float('nan'))])
def test_invalid_current_conditions_cannot_generate_advice(field, value):
    args = dict(load_mw=550, capacity_mw=600, current_o2=4, current_flue_temp=135, current_fly_ash_carbon=3)
    args[field] = value
    with pytest.raises(ValueError):
        CombustionOptimizer().recommend(**args)


def test_holdout_labels_are_not_used_to_refit_the_served_model():
    first = CombustionOptimizer().fit(good_samples())
    modified = good_samples()
    for row in modified[48:]:
        row['net_coal_rate'] += .5
    second = CombustionOptimizer().fit(modified)
    assert second.fitted
    assert second.predict_coal_rate(550, 4, 135, 3) == pytest.approx(first.predict_coal_rate(550, 4, 135, 3))
    assert second.evaluation['validation_mae'] == pytest.approx(.5)


def test_candidate_o2_must_also_stay_inside_training_range():
    rows = good_samples()
    for row in rows:
        row['flue_o2'] += 2
    opt = CombustionOptimizer().fit(rows)
    assert opt.fitted
    result = opt.recommend(load_mw=550, capacity_mw=600, current_o2=5,
                           current_flue_temp=135, current_fly_ash_carbon=3)
    assert result.evaluation['reason'] == 'OUTSIDE_TRAINING_RANGE'
