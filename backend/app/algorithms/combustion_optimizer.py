"""AI 燃烧寻优。

目标：在给定负荷与煤质下，给出能把供电煤耗压到最低的运行调整（首要是配风/氧量）。
做法是数据驱动 + 机理先验双保险：
  · 有足够历史样本时，用多元线性回归（最小二乘）拟合"煤耗 = f(负荷, 氧量, 排烟温度, 飞灰含碳量)"，
    回归系数即各参数对煤耗的边际影响，据此寻优；
  · 样本不足时退回机理先验——最优氧量随负荷升高而降低（高负荷炉膛充满度好、漏风占比小）。
两条路都指向同一件事：把多余的过量空气拧下来，少让烟气白白带走热。
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite

import numpy as np

MODEL_VERSION = "combustion-lr-v2"
PRIOR_VERSION = "combustion-prior-v2"


def optimal_o2_for_load(load_mw: float, capacity_mw: float) -> float:
    """最优烟气含氧量设定值（%）：负荷越高、最优氧量越低。"""
    ratio = min(max(load_mw / max(capacity_mw, 1.0), 0.3), 1.0)
    return round(min(max(6.0 - 3.0 * ratio, 2.5), 5.0), 2)


def _mill_combo(load_mw: float, capacity_mw: float) -> str:
    ratio = load_mw / max(capacity_mw, 1.0)
    if ratio >= 0.85:
        return "投运 A/B/C/D/E 五磨，下层为主稳燃"
    if ratio >= 0.6:
        return "投运 A/B/C/D 四磨，停运最上层磨"
    return "投运 B/C/D 三磨，集中下层、保火检稳定"


def _secondary_air(rec_o2: float, current_o2: float) -> str:
    if current_o2 - rec_o2 > 0.3:
        return f"逐步关小二次风总挡板，把氧量由 {current_o2:.1f}% 收至 {rec_o2:.1f}%"
    if rec_o2 - current_o2 > 0.3:
        return f"适当开大二次风，把氧量由 {current_o2:.1f}% 提至 {rec_o2:.1f}% 防结焦"
    return "维持当前配风，氧量已接近最优"


@dataclass(slots=True)
class OptimizationResult:
    recommended_o2: float
    predicted_coal_rate_drop: float
    secondary_air: str
    mill_combo: str
    confidence: float
    model_version: str
    rationale: str
    evaluation: dict


class CombustionOptimizer:
    """煤耗代理模型 + 寻优器。"""

    FEATURES = ("load_mw", "flue_o2", "flue_gas_temp", "fly_ash_carbon")

    def __init__(self, o2_sensitivity: float = 1.2, fly_ash_target: float = 2.5) -> None:
        self.o2_sensitivity = o2_sensitivity
        self.fly_ash_target = fly_ash_target
        self._coef: np.ndarray | None = None
        self._mean: np.ndarray | None = None
        self._scale: np.ndarray | None = None
        self._ranges: np.ndarray | None = None
        self.evaluation = self._empty_evaluation()

    @staticmethod
    def _empty_evaluation():
        return dict(mode='PRIOR', reason='NO_HISTORY', valid_samples=0, rejected_samples=0,
                    train_samples=0, validation_samples=0, validation_mae=None, baseline_mae=None,
                    dataset_sha256=None, validation_method='chronological_holdout_20pct',
                    policy={'min_samples': 24, 'max_mae_g_kwh': 5.0, 'min_baseline_improvement': 0.1})

    @staticmethod
    def _valid_features(values):
        load, o2, temp, fly = values
        return (all(isfinite(v) for v in values) and 0 < load <= 2000
                and 0 <= o2 <= 21 and 0 <= temp <= 1000 and 0 <= fly < 100)

    @property
    def fitted(self) -> bool:
        return self._coef is not None

    def fit(self, samples: list[dict]) -> "CombustionOptimizer":
        """输入按时间升序；前80%拟合，后20%只评估，失败则丢弃旧模型。"""
        self._coef = self._mean = self._scale = self._ranges = None
        self.evaluation = self._empty_evaluation()
        rows = []
        for sample in samples:
            try:
                values = [float(sample[f]) for f in (*self.FEATURES, 'net_coal_rate')]
                if any(isinstance(sample[f], bool) for f in (*self.FEATURES, 'net_coal_rate')):
                    continue
                if not self._valid_features(values[:4]) or not isfinite(values[4]) or not 0 < values[4] <= 2000:
                    continue
                rows.append(values)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
        self.evaluation.update(valid_samples=len(rows), rejected_samples=len(samples) - len(rows),
            dataset_sha256=sha256(json.dumps(rows, separators=(',', ':'), allow_nan=False).encode()).hexdigest())
        if len(rows) < 24:
            self.evaluation['reason'] = 'INSUFFICIENT_HISTORY'
            return self
        data = np.array(rows)
        split = int(len(rows) * .8)
        x_train, y_train = data[:split, :4], data[:split, 4]
        x_test, y_test = data[split:, :4], data[split:, 4]
        self.evaluation.update(train_samples=split, validation_samples=len(rows) - split)
        mean, scale = x_train.mean(axis=0), x_train.std(axis=0)
        if np.any(scale < 1e-10):
            self.evaluation['reason'] = 'RANK_DEFICIENT'
            return self
        design = np.column_stack([np.ones(split), (x_train - mean) / scale])
        try:
            coef, _, rank, _ = np.linalg.lstsq(design, y_train, rcond=None)
        except np.linalg.LinAlgError:
            self.evaluation['reason'] = 'FIT_FAILED'
            return self
        if rank < 5:
            self.evaluation['reason'] = 'RANK_DEFICIENT'
            return self
        prediction = np.column_stack([np.ones(len(y_test)), (x_test - mean) / scale]) @ coef
        mae = float(np.mean(np.abs(y_test - prediction)))
        baseline_mae = float(np.mean(np.abs(y_test - y_train.mean())))
        if not all(isfinite(v) for v in (mae, baseline_mae)):
            self.evaluation['reason'] = 'FIT_FAILED'
            return self
        self.evaluation.update(validation_mae=mae, baseline_mae=baseline_mae)
        if mae > 5 or baseline_mae < 1e-8 or mae >= baseline_mae * .9:
            self.evaluation['reason'] = 'VALIDATION_FAILED'
            return self
        self._coef, self._mean, self._scale = coef, mean, scale
        self._ranges = np.column_stack([x_train.min(axis=0), x_train.max(axis=0)])
        self.evaluation.update(mode='REGRESSION', reason='VALIDATED',
            feature_ranges={f: list(map(float, bounds)) for f, bounds in zip(self.FEATURES, self._ranges)},
            coefficients={f: float(c) for f, c in zip(self.FEATURES, coef[1:] / scale)},
            intercept=float(coef[0] - np.dot(coef[1:], mean / scale)))
        return self

    def predict_coal_rate(
        self, load_mw: float, flue_o2: float, flue_gas_temp: float, fly_ash_carbon: float
    ) -> float | None:
        if self._coef is None:
            return None
        values = np.array([load_mw, flue_o2, flue_gas_temp, fly_ash_carbon])
        if not self._within_range(values):
            return None
        x = np.r_[1., (values - self._mean) / self._scale]
        return float(x @ self._coef)

    def _within_range(self, values):
        return (self._ranges is not None and bool(np.all(np.isfinite(values)))
                and bool(np.all(values >= self._ranges[:, 0]) and np.all(values <= self._ranges[:, 1])))

    def recommend(
        self,
        *,
        load_mw: float,
        capacity_mw: float,
        current_o2: float,
        current_flue_temp: float,
        current_fly_ash_carbon: float,
    ) -> OptimizationResult:
        values = [load_mw, current_o2, current_flue_temp, current_fly_ash_carbon]
        if not self._valid_features(values) or not isfinite(capacity_mw) or capacity_mw <= 0 or load_mw > capacity_mw:
            raise ValueError('当前工况必须有限且在有效范围内，负荷须大于零且不超过机组容量')
        rec_o2 = optimal_o2_for_load(load_mw, capacity_mw)
        o2_gap = current_o2 - rec_o2  # 正=当前氧量偏高，有下调空间
        evaluation = dict(self.evaluation)
        evaluation['current_features'] = dict(zip(self.FEATURES, values))
        use_regression = self.fitted and self._within_range(np.array(values)) and self._within_range(
            np.array([load_mw, rec_o2, current_flue_temp, current_fly_ash_carbon]))
        if self.fitted and not use_regression:
            evaluation.update(mode='PRIOR', reason='OUTSIDE_TRAINING_RANGE')

        # 氧量下调带来的煤耗收益
        if use_regression:
            coef_o2 = self._coef[2] / self._scale[1]
            o2_drop = max(0.0, coef_o2 * o2_gap)
            confidence = round(min(0.95, 1 - evaluation['validation_mae'] / evaluation['baseline_mae']), 2)
        else:
            o2_drop = max(0.0, self.o2_sensitivity * o2_gap)
            confidence = 0.0  # 经验规则没有经过样本外验证，不能标成统计置信概率。

        # 飞灰含碳量偏高时，配合磨煤机细度/分离器调整还能再抠一点
        fly_excess = max(0.0, current_fly_ash_carbon - self.fly_ash_target)
        fly_drop = 1.8 * fly_excess * 0.3

        total_drop = round(o2_drop + fly_drop, 2)
        rationale = (
            f"负荷 {load_mw:.0f}MW 对应最优氧量约 {rec_o2:.1f}%，当前 {current_o2:.1f}%。"
            f"{'下调过量空气可减小排烟热损失；' if o2_gap > 0.3 else ''}"
            f"{'飞灰含碳量偏高，建议同步优化磨煤机细度。' if fly_excess > 0.3 else ''}"
        ).strip()
        rationale += f" 依据模式：{evaluation['mode']}；评估原因：{evaluation['reason']}。收益为估算，需人工验证。"
        return OptimizationResult(
            recommended_o2=rec_o2,
            predicted_coal_rate_drop=total_drop,
            secondary_air=_secondary_air(rec_o2, current_o2),
            mill_combo=_mill_combo(load_mw, capacity_mw),
            confidence=confidence,
            model_version=MODEL_VERSION if use_regression else PRIOR_VERSION,
            rationale=rationale,
            evaluation=evaluation,
        )


def optimize_combustion(
    *,
    load_mw: float,
    capacity_mw: float,
    current_o2: float,
    current_flue_temp: float,
    current_fly_ash_carbon: float,
    history: list[dict] | None = None,
) -> OptimizationResult:
    """便捷入口：可选传入历史样本即时拟合后给建议。"""
    optimizer = CombustionOptimizer()
    if history:
        optimizer.fit(history)
    return optimizer.recommend(
        load_mw=load_mw,
        capacity_mw=capacity_mw,
        current_o2=current_o2,
        current_flue_temp=current_flue_temp,
        current_fly_ash_carbon=current_fly_ash_carbon,
    )
