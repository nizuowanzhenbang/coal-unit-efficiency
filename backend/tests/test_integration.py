"""跨系统集成端点测试。"""

from __future__ import annotations

from app.config import settings


def test_health(client):
    resp = client.get("/api/integration/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "coal-unit-efficiency"


def test_receive_coal_lhv_requires_secret(client):
    resp = client.post("/api/integration/coal-lhv", json={"unit_code": "U-01", "coal_lhv": 21000})
    assert resp.status_code == 401


def test_receive_coal_lhv_wrong_secret(client):
    resp = client.post(
        "/api/integration/coal-lhv",
        json={"unit_code": "U-01", "coal_lhv": 21000},
        headers={"X-Integration-Secret": "nope"},
    )
    assert resp.status_code == 401


def test_receive_and_get_cached_lhv(client):
    resp = client.post(
        "/api/integration/coal-lhv",
        json={"unit_code": "U-77", "coal_lhv": 22100},
        headers={"X-Integration-Secret": settings.integration_secret},
    )
    assert resp.status_code == 200
    cached = client.get("/api/integration/coal-lhv/U-77")
    assert cached.json()["coal_lhv"] == 22100


def test_get_uncached_lhv_none(client):
    resp = client.get("/api/integration/coal-lhv/UNKNOWN")
    assert resp.json()["coal_lhv"] is None


def test_app_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
