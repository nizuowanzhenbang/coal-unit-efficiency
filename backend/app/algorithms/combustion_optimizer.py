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

import numpy as np

MODEL_VERSION = "combustion-lr-v1"


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


class CombustionOptimizer:
    """煤耗代理模型 + 寻优器。"""

    FEATURES = ("load_mw", "flue_o2", "flue_gas_temp", "fly_ash_carbon")

    def __init__(self, o2_sensitivity: float = 1.2, fly_ash_target: float = 2.5) -> None:
        self.o2_sensitivity = o2_sensitivity
        self.fly_ash_target = fly_ash_target
        self._coef: np.ndarray | None = None
        self._r2: float = 0.0

    @property
    def fitted(self) -> bool:
        return self._coef is not None

    def fit(self, samples: list[dict]) -> "CombustionOptimizer":
        """用历史样本拟合线性煤耗模型；样本过少则保持未拟合（走机理先验）。"""
        rows = [s for s in samples if s.get("net_coal_rate")]
        if len(rows) < 8:
            return self
        x = np.array([[1.0] + [float(r[f]) for f in self.FEATURES] for r in rows])
        y = np.array([float(r["net_coal_rate"]) for r in rows])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        pred = x @ coef
        ss_res = float(np.sum((y - pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
        self._coef = coef
        self._r2 = max(0.0, 1.0 - ss_res / ss_tot)
        return self

    def predict_coal_rate(
        self, load_mw: float, flue_o2: float, flue_gas_temp: float, fly_ash_carbon: float
    ) -> float | None:
        if self._coef is None:
            return None
        x = np.array([1.0, load_mw, flue_o2, flue_gas_temp, fly_ash_carbon])
        return float(x @ self._coef)

    def recommend(
        self,
        *,
        load_mw: float,
        capacity_mw: float,
        current_o2: float,
        current_flue_temp: float,
        current_fly_ash_carbon: float,
    ) -> OptimizationResult:
        rec_o2 = optimal_o2_for_load(load_mw, capacity_mw)
        o2_gap = current_o2 - rec_o2  # 正=当前氧量偏高，有下调空间

        # 氧量下调带来的煤耗收益
        if self.fitted and self._coef is not None:
            coef_o2 = self._coef[2]  # flue_o2 的回归系数
            o2_drop = max(0.0, coef_o2 * o2_gap)
            confidence = round(min(0.95, 0.55 + 0.4 * self._r2), 2)
        else:
            o2_drop = max(0.0, self.o2_sensitivity * o2_gap)
            confidence = 0.6

        # 飞灰含碳量偏高时，配合磨煤机细度/分离器调整还能再抠一点
        fly_excess = max(0.0, current_fly_ash_carbon - self.fly_ash_target)
        fly_drop = 1.8 * fly_excess * 0.3

        total_drop = round(o2_drop + fly_drop, 2)
        rationale = (
            f"负荷 {load_mw:.0f}MW 对应最优氧量约 {rec_o2:.1f}%，当前 {current_o2:.1f}%。"
            f"{'下调过量空气可减小排烟热损失；' if o2_gap > 0.3 else ''}"
            f"{'飞灰含碳量偏高，建议同步优化磨煤机细度。' if fly_excess > 0.3 else ''}"
        ).strip()
        return OptimizationResult(
            recommended_o2=rec_o2,
            predicted_coal_rate_drop=total_drop,
            secondary_air=_secondary_air(rec_o2, current_o2),
            mill_combo=_mill_combo(load_mw, capacity_mw),
            confidence=confidence,
            model_version=MODEL_VERSION,
            rationale=rationale,
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
