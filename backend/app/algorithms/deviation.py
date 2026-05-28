"""耗差分析：把运行小指标的偏差翻译成"多烧了多少煤"。

电厂运行人员盯着几十个表计，但"排烟温度高了 8℃"到底意味着什么？耗差分析
用灵敏度系数把每个指标的偏差折算成供电煤耗影响（g/kWh），让运行调整有的放矢。
灵敏度为某负荷段经验值，可被机组级对标基准覆盖。
"""

from __future__ import annotations

from dataclasses import dataclass

LOWER_BETTER = "LOWER_BETTER"
HIGHER_BETTER = "HIGHER_BETTER"

# 典型 600MW 级机组耗差灵敏度（g/kWh 每单位偏差）
DEFAULT_SENSITIVITIES: dict[str, dict] = {
    "flue_gas_temp": {"label": "排烟温度", "unit": "℃", "sens": 0.22, "direction": LOWER_BETTER},
    "flue_o2": {"label": "烟气含氧量", "unit": "%", "sens": 1.2, "direction": LOWER_BETTER},
    "fly_ash_carbon": {"label": "飞灰含碳量", "unit": "%", "sens": 1.8, "direction": LOWER_BETTER},
    "main_steam_temp": {"label": "主蒸汽温度", "unit": "℃", "sens": 0.13, "direction": HIGHER_BETTER},
    "reheat_steam_temp": {"label": "再热汽温", "unit": "℃", "sens": 0.12, "direction": HIGHER_BETTER},
    "condenser_vacuum": {"label": "凝汽器真空", "unit": "kPa", "sens": 3.0, "direction": LOWER_BETTER},
    "aux_ratio": {"label": "厂用电率", "unit": "%", "sens": 3.1, "direction": LOWER_BETTER},
}


@dataclass(slots=True)
class DeviationResult:
    indicator: str
    label: str
    unit: str
    actual: float
    target: float
    deviation: float
    coal_rate_impact: float
    severity: str


def coal_rate_impact(actual: float, target: float, sensitivity: float, direction: str) -> float:
    """折算煤耗影响：朝"变差"方向偏离记为正（多烧），反向记为负（节约）。"""
    raw = actual - target
    if direction == HIGHER_BETTER:
        raw = -raw
    return raw * sensitivity


def classify_severity(impact: float) -> str:
    a = abs(impact)
    if a < 0.5:
        return "NORMAL"
    if a < 2.0:
        return "WATCH"
    return "ALERT"


def analyze_indicator(
    indicator: str,
    actual: float,
    target: float,
    *,
    sensitivity: float | None = None,
    direction: str | None = None,
    label: str | None = None,
    unit: str | None = None,
) -> DeviationResult:
    meta = DEFAULT_SENSITIVITIES.get(indicator, {})
    sens = sensitivity if sensitivity is not None else meta.get("sens", 0.0)
    dirn = direction or meta.get("direction", LOWER_BETTER)
    impact = coal_rate_impact(actual, target, sens, dirn)
    return DeviationResult(
        indicator=indicator,
        label=label or meta.get("label", indicator),
        unit=unit or meta.get("unit", ""),
        actual=round(actual, 3),
        target=round(target, 3),
        deviation=round(actual - target, 3),
        coal_rate_impact=round(impact, 3),
        severity=classify_severity(impact),
    )


def total_impact(results: list[DeviationResult]) -> float:
    """耗差合计 g/kWh（正=相对目标整体偏高）。"""
    return round(sum(r.coal_rate_impact for r in results), 3)
