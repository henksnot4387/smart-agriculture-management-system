from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.security import require_api_token
from app.repositories.sensor import SensorQueryRepository
from app.schemas.sensor import (
    SensorBucket,
    SensorDashboardResponse,
    SensorRange,
    SensorRawResponse,
    SensorSeriesResponse,
)
from app.services.sensor import SensorQueryService

router = APIRouter(
    prefix="/api/sensor",
    tags=["sensor"],
    dependencies=[Depends(require_api_token)],
)


@lru_cache
def get_sensor_query_service() -> SensorQueryService:
    return SensorQueryService(
        settings=settings,
        repository=SensorQueryRepository(settings),
    )


@router.get("/raw", response_model=SensorRawResponse)
async def get_raw_sensor_samples(
    start: datetime | None = None,
    end: datetime | None = None,
    zone: str | None = None,
    metrics: str | None = None,
    limit: int = Query(default=5000, ge=1, le=20000),
    provider: str | None = None,
    service: SensorQueryService = Depends(get_sensor_query_service),
) -> SensorRawResponse:
    return service.get_raw(
        start=start,
        end=end,
        zone=zone,
        metrics_query=metrics,
        limit=limit,
        provider=provider,
    )


@router.get("/series", response_model=SensorSeriesResponse)
async def get_sensor_series(
    range: SensorRange | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    zone: str | None = None,
    metrics: str | None = None,
    bucket: SensorBucket = SensorBucket.AUTO,
    provider: str | None = None,
    service: SensorQueryService = Depends(get_sensor_query_service),
) -> SensorSeriesResponse:
    return service.get_series(
        range_query=range,
        start=start,
        end=end,
        zone=zone,
        metrics_query=metrics,
        bucket_query=bucket,
        provider=provider,
    )


@router.get("/dashboard", response_model=SensorDashboardResponse, response_model_exclude_none=True)
async def get_sensor_dashboard(
    range: SensorRange = SensorRange.LAST_24_HOURS,
    zone: str | None = None,
    provider: str | None = None,
    service: SensorQueryService = Depends(get_sensor_query_service),
) -> SensorDashboardResponse:
    return service.get_dashboard(
        range_query=range,
        zone=zone,
        provider=provider,
    )
