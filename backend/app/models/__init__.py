"""ORM 模型聚合导出，导入本包即完成全部表注册。"""

from .alert import Alert
from .analysis import BenchmarkTarget, DeviationAnalysis, OptimizationSuggestion
from .operation import EfficiencyRecord, OperatingSnapshot
from .report import EnergyReport
from .unit import CoalUnit
from .user import Role, User

__all__ = [
    "Alert",
    "BenchmarkTarget",
    "DeviationAnalysis",
    "OptimizationSuggestion",
    "EfficiencyRecord",
    "OperatingSnapshot",
    "EnergyReport",
    "CoalUnit",
    "Role",
    "User",
]
