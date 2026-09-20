"""数据库引擎与会话工厂。"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表。导入 models 触发 ORM 注册后再 create_all。"""
    from . import models  # noqa: F401  确保所有表完成注册

    Base.metadata.create_all(bind=engine)
    ensure_evaluation_column(engine)


def ensure_evaluation_column(bind) -> None:
    """无损补齐评估快照列；旧建议保持 NULL，不伪造历史评估。"""
    with bind.begin() as conn:
        columns = {c['name'] for c in inspect(conn).get_columns('optimization_suggestions')}
        if 'evaluation' not in columns:
            conn.execute(text('ALTER TABLE optimization_suggestions ADD COLUMN evaluation JSON'))
