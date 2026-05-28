"""业务编号生成：按"前缀-日期-序号"规则生成唯一编号。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session


def next_code(
    db: Session, model, code_attr, prefix: str, *, date_fmt: str = "%Y%m%d", width: int = 4
) -> str:
    """生成形如 PREFIX-20260528-0001 的编号（按当天前缀计数递增）。"""
    stamp = datetime.now(timezone.utc).strftime(date_fmt)
    head = f"{prefix}-{stamp}-"
    count = db.query(func.count()).select_from(model).filter(code_attr.like(f"{head}%")).scalar() or 0
    return f"{head}{count + 1:0{width}d}"
