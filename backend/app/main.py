"""应用装配入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .database import SessionLocal, init_db
from .routers import (
    alerts,
    auth,
    benchmark,
    dashboard,
    deviation,
    efficiency,
    integration,
    optimization,
    reports,
    snapshots,
    units,
    users,
)
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)

_ROUTERS = (
    auth.router,
    users.router,
    units.router,
    snapshots.router,
    efficiency.router,
    benchmark.router,
    deviation.router,
    optimization.router,
    reports.router,
    alerts.router,
    dashboard.router,
    integration.router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.auto_seed:
        from .models.user import User
        from .seed_data import seed

        db = SessionLocal()
        try:
            if db.query(User).count() == 0:
                seed(db)
                logging.getLogger("startup").info("演示数据已注入")
        finally:
            db.close()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in _ROUTERS:
    app.include_router(r, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict:
    return {"app": settings.app_name, "version": __version__, "docs": "/docs"}


@app.get(f"{settings.api_prefix}/health")
def health() -> dict:
    return {"status": "ok"}
