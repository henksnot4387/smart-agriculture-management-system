from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.security import require_api_token
from app.repositories.ops import OpsRepository
from app.schemas.ops import OpsCatalogResponse, OpsLiveResponse, OpsTrendsResponse
from app.services.ops import OpsService

router = APIRouter(
    prefix="/api/ops",
    tags=["ops"],
    dependencies=[Depends(require_api_token)],
)


@lru_cache
def get_ops_service() -> OpsService:
    return OpsService(
        settings=settings,
        repository=OpsRepository(settings),
    )


@router.get("/catalog", response_model=OpsCatalogResponse)
def get_ops_catalog(
    provider: str | None = Query(default=None),
    lookbackHours: int = Query(default=24, ge=1, le=168),
    service: OpsService = Depends(get_ops_service),
) -> OpsCatalogResponse:
    return service.get_catalog(provider=provider, lookback_hours=lookbackHours)


@router.get("/live", response_model=OpsLiveResponse)
def get_ops_live(
    provider: str | None = Query(default=None),
    lookbackHours: int = Query(default=24, ge=1, le=168),
    service: OpsService = Depends(get_ops_service),
) -> OpsLiveResponse:
    return service.get_live(provider=provider, lookback_hours=lookbackHours)


@router.get("/trends", response_model=OpsTrendsResponse)
def get_ops_trends(
    provider: str | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    zone: str | None = Query(default=None),
    service: OpsService = Depends(get_ops_service),
) -> OpsTrendsResponse:
    return service.get_trends(provider=provider, hours=hours, zone=zone)
