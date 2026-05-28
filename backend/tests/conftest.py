"""测试基础设施：独立 sqlite 测试库 + 每个用例隔离 + 角色令牌工具。"""

from __future__ import annotations

import os

os.environ.setdefault("CUE_DATABASE_URL", "sqlite:///./test_coal_unit_efficiency.db")
os.environ["CUE_ENABLE_SCHEDULER"] = "false"
os.environ["CUE_AUTO_SEED"] = "false"

from collections.abc import Callable, Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.unit import CoalUnit  # noqa: E402
from app.models.user import Role, User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def token_for(db: Session) -> Callable[[Role], dict[str, str]]:
    def _make(role: Role) -> dict[str, str]:
        username = f"u_{role.value.lower()}"
        if db.query(User).filter(User.username == username).first() is None:
            db.add(
                User(
                    username=username,
                    full_name=role.value,
                    role=role.value,
                    hashed_password=hash_password("pw"),
                )
            )
            db.commit()
        token = create_access_token(username, role.value)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def admin_headers(token_for) -> dict[str, str]:
    return token_for(Role.ADMIN)


@pytest.fixture
def eng_headers(token_for) -> dict[str, str]:
    return token_for(Role.ENERGY_ENG)


@pytest.fixture
def operator_headers(token_for) -> dict[str, str]:
    return token_for(Role.OPERATOR)


@pytest.fixture
def viewer_headers(token_for) -> dict[str, str]:
    return token_for(Role.VIEWER)


@pytest.fixture
def unit_factory(db: Session) -> Callable[..., CoalUnit]:
    counter = {"n": 0}

    def _make(**overrides) -> CoalUnit:
        counter["n"] += 1
        defaults = dict(
            code=f"U-{counter['n']:02d}",
            name=f"测试机组{counter['n']}",
            capacity_mw=600.0,
            design_net_coal_rate=300.0,
            design_boiler_eff=93.0,
            design_pipe_eff=99.0,
            design_turbine_eff=45.0,
            design_aux_ratio=5.5,
            design_ash_ar=15.0,
            design_coal_lhv=21000.0,
        )
        defaults.update(overrides)
        unit = CoalUnit(**defaults)
        db.add(unit)
        db.commit()
        db.refresh(unit)
        return unit

    return _make


def make_snapshot_payload(unit_id: int, **overrides) -> dict:
    payload = dict(
        unit_id=unit_id,
        load_mw=560.0,
        main_steam_temp=538.0,
        main_steam_press=16.7,
        reheat_steam_temp=538.0,
        feedwater_temp=275.0,
        flue_gas_temp=125.0,
        flue_o2=3.6,
        fly_ash_carbon=2.5,
        slag_carbon=5.0,
        condenser_vacuum=4.8,
        ambient_temp=20.0,
        coal_flow_tph=240.0,
        coal_lhv=21000.0,
        aux_power_mw=30.0,
    )
    payload.update(overrides)
    return payload
