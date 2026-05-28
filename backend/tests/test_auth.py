"""认证与 RBAC 测试。"""

from __future__ import annotations

from app.models.user import Role, User
from app.security import hash_password


def _make_user(db, username="alice", role=Role.ENERGY_ENG, password="secret"):
    user = User(username=username, full_name="A", role=role.value, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return user


def test_login_success(client, db):
    _make_user(db, "alice", Role.ENERGY_ENG, "secret")
    resp = client.post("/api/auth/login", data={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["role"] == "ENERGY_ENG"


def test_login_wrong_password(client, db):
    _make_user(db, "bob", password="right")
    resp = client.post("/api/auth/login", data={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401


def test_login_inactive(client, db):
    user = _make_user(db, "carol")
    user.is_active = False
    db.commit()
    resp = client.post("/api/auth/login", data={"username": "carol", "password": "secret"})
    assert resp.status_code == 403


def test_me_returns_profile(client, eng_headers):
    resp = client.get("/api/auth/me", headers=eng_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "ENERGY_ENG"


def test_protected_without_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_admin_only_forbidden_for_viewer(client, viewer_headers):
    resp = client.get("/api/users", headers=viewer_headers)
    assert resp.status_code == 403


def test_admin_can_list_users(client, admin_headers):
    resp = client.get("/api/users", headers=admin_headers)
    assert resp.status_code == 200


def test_admin_role_bypasses_specific_role_gate(client, admin_headers):
    # ADMIN 应能访问需要 ENERGY_ENG 的接口
    resp = client.get("/api/benchmarks", headers=admin_headers)
    assert resp.status_code == 200
