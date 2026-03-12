from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.integrations.hoogendoorn.dependencies import get_hoogendoorn_service
from app.integrations.hoogendoorn.mock_provider import MockHoogendoornProvider
from app.integrations.hoogendoorn.service import HoogendoornSyncService

router = APIRouter(tags=["hoogendoorn"])


class SyncRequest(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    lookback_minutes: int | None = Field(default=None, ge=1, le=1440)


class MockFailureRequest(BaseModel):
    count: int = Field(ge=0, le=20)


def require_admin_token(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> None:
    configured_token = settings.backend_admin_token.strip()
    if not configured_token:
        # Keep local dev friction low; in non-development environments
        # this should be explicitly configured.
        if settings.app_env.lower() in {"production", "prod"}:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="BACKEND_ADMIN_TOKEN is required in production.",
            )
        return
    if x_admin_token != configured_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token.")


@router.get("/status")
async def hoogendoorn_status(
    service: HoogendoornSyncService = Depends(get_hoogendoorn_service),
) -> dict[str, object]:
    return await service.status()


@router.post("/sync")
async def trigger_hoogendoorn_sync(
    payload: SyncRequest | None = None,
    service: HoogendoornSyncService = Depends(get_hoogendoorn_service),
    _: None = Depends(require_admin_token),
) -> dict[str, object]:
    payload = payload or SyncRequest()
    return await service.sync(
        start=payload.start,
        end=payload.end,
        lookback_minutes=payload.lookback_minutes,
    )


@router.post("/mock/failures")
async def configure_mock_failures(
    payload: MockFailureRequest,
    service: HoogendoornSyncService = Depends(get_hoogendoorn_service),
    _: None = Depends(require_admin_token),
) -> dict[str, object]:
    provider = service.provider
    if not isinstance(provider, MockHoogendoornProvider):
        raise HTTPException(status_code=400, detail="Mock failure simulation is only available in mock provider mode.")

    remaining = provider.set_failures_remaining(payload.count)
    return {
        "provider": provider.provider_name,
        "failures_remaining": remaining,
    }
