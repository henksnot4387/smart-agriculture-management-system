from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.repositories.user import UserRepository

ALL_ROLES = {"SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"}


@dataclass(frozen=True)
class ActorContext:
    user_id: str
    role: str
    email: str | None
    name: str | None


def get_user_repository() -> UserRepository:
    return UserRepository(settings)


def _validate_user_id(raw_user_id: str | None) -> str:
    user_id = (raw_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-User-Id header.")
    try:
        UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="X-User-Id must be a valid UUID.") from exc
    return user_id


def _validate_user_role(raw_role: str | None) -> str:
    role = (raw_role or "").strip().upper()
    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-User-Role header.")
    if role not in ALL_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid user role.")
    return role


def require_actor(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    repository: UserRepository = Depends(get_user_repository),
) -> ActorContext:
    role = _validate_user_role(x_user_role)
    user_id = _validate_user_id(x_user_id)

    user = repository.get_active_user(user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    if not bool(user.get("is_active")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive.")

    db_role = str(user.get("role") or "").upper()
    if db_role != role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role mismatch.")

    return ActorContext(
        user_id=user_id,
        role=role,
        email=user.get("email"),
        name=user.get("name"),
    )


def require_roles(allowed_roles: set[str]) -> Callable[[ActorContext], ActorContext]:
    normalized = {role.upper() for role in allowed_roles}

    def _dependency(actor: ActorContext = Depends(require_actor)) -> ActorContext:
        if actor.role not in normalized:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
        return actor

    return _dependency
