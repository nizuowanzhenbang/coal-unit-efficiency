"""FastAPI 依赖：当前用户解析 + 角色门禁。"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models.user import Role, User
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="无效或过期的凭证",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise _CRED_EXC
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if user is None or not user.is_active:
        raise _CRED_EXC
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed: Iterable[str] = {r.value for r in roles}

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role == Role.ADMIN.value or user.role in allowed:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要角色之一：{sorted(allowed)}",
        )

    return _checker
