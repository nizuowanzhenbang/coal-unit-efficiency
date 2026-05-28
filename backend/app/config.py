"""运行期配置。所有可调项集中在此，环境变量优先。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CUE_", env_file=".env", extra="ignore")

    app_name: str = "燃煤机组能效与智能燃烧优化系统"
    api_prefix: str = "/api"

    # 数据库：默认 sqlite，生产用 postgres（docker-compose 注入 CUE_DATABASE_URL）
    database_url: str = "sqlite:///./coal_unit_efficiency.db"

    # JWT
    secret_key: str = "change-me-in-prod-coal-unit-efficiency-2026"
    access_token_expire_minutes: int = 60 * 12
    jwt_algorithm: str = "HS256"

    # 标准煤低位发热量（kJ/kg），煤量折标煤、煤耗换算的基准
    standard_coal_lhv: float = 29307.0
    # 标煤单价（元/吨），用于节煤金额测算
    standard_coal_price: float = 850.0
    # 每吨标煤燃烧 CO2 排放因子（tCO2/t标煤），用于减碳量测算
    co2_factor: float = 2.66

    # 调度作业开关（测试环境关闭，避免后台线程干扰）
    enable_scheduler: bool = True
    efficiency_calc_interval_min: int = 1
    deviation_scan_interval_min: int = 5

    # 启动时若库为空自动注入演示数据（docker-compose 默认开启）
    auto_seed: bool = False

    # 前端跨域来源
    cors_origins: str = "*"

    # 跨系统集成
    integration_secret: str = "plant-suite-shared-secret"
    integration_timeout_s: float = 3.0
    coal_quality_url: str = ""        # ← 煤质化验系统：拉取入炉煤低位发热量
    inspection_url: str = ""          # → 设备点检：能效异常转设备缺陷
    safety_url: str = ""              # → 安全生产：重大能耗事件转安全事件

    # 演示账号统一口令
    demo_password: str = "demo123"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
