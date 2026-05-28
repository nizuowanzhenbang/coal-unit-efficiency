"""跨系统集成出库客户端。

智慧电厂套件里各子系统通过共享密钥头互相推送事件。本子系统：
  → 设备点检：能效持续恶化疑似设备问题（如空预器堵灰致排烟温度高）转设备缺陷
  → 安全生产：重大能耗异常事件备案
失败不阻断主流程——集成是"锦上添花"，超时即放弃并记日志。
"""

from __future__ import annotations

import logging
import time

import httpx

from ..config import settings

logger = logging.getLogger("integration")


def _post(url: str, payload: dict) -> bool:
    if not url:
        return False
    headers = {"X-Integration-Secret": settings.integration_secret}
    for attempt in range(2):
        try:
            resp = httpx.post(
                url, json=payload, headers=headers, timeout=settings.integration_timeout_s
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("集成推送失败(%s/2) %s: %s", attempt + 1, url, exc)
            time.sleep(0.2 * (attempt + 1))
    return False


def push_defect_to_inspection(*, unit_code: str, title: str, detail: str) -> bool:
    """能效异常→设备点检系统生成缺陷工单。"""
    return _post(
        settings.inspection_url,
        {"source": "coal-unit-efficiency", "equipment_code": unit_code, "title": title, "detail": detail},
    )


def push_event_to_safety(*, unit_code: str, level: str, title: str, detail: str) -> bool:
    """重大能耗事件→安全生产系统备案。"""
    return _post(
        settings.safety_url,
        {"source": "coal-unit-efficiency", "unit_code": unit_code, "level": level, "title": title, "detail": detail},
    )


def fetch_coal_lhv(unit_code: str) -> float | None:
    """← 煤质化验系统：拉取该机组入炉煤最新低位发热量 kJ/kg。"""
    if not settings.coal_quality_url:
        return None
    headers = {"X-Integration-Secret": settings.integration_secret}
    try:
        resp = httpx.get(
            f"{settings.coal_quality_url}/api/integration/latest-lhv",
            params={"unit_code": unit_code},
            headers=headers,
            timeout=settings.integration_timeout_s,
        )
        resp.raise_for_status()
        return float(resp.json().get("coal_lhv"))
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("拉取煤质热值失败 %s: %s", unit_code, exc)
        return None
