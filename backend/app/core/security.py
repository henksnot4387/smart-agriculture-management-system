from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_api_token(x_api_token: str | None = Header(default=None, alias="X-API-Token")) -> None:
    configured_token = settings.backend_api_token.strip()
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BACKEND_API_TOKEN is required for protected backend APIs.",
        )
    if x_api_token != configured_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token.")
