from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SensorMetric(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    EC = "ec"
    PH = "ph"


class SensorRange(str, Enum):
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"


class SensorBucket(str, Enum):
    AUTO = "auto"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    ONE_DAY = "1d"


class RawSensorSample(BaseModel):
    recordedAtUtc: datetime
    recordedAtLocal: datetime
    utcOffsetMinutes: int
    zone: str
    deviceId: str
    metric: SensorMetric
    value: float
    provider: str | None = None
    source: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class SensorRawResponse(BaseModel):
    startUtc: datetime
    endUtc: datetime
    zone: str | None = None
    provider: str | None = None
    metrics: list[SensorMetric]
    timezone: str = "Asia/Shanghai"
    storageTimezone: str = "UTC"
    items: list[RawSensorSample] = Field(default_factory=list)


class MetricSeriesPoint(BaseModel):
    bucketStartUtc: datetime
    bucketStartLocal: datetime
    avg: float
    min: float
    max: float
    count: int


class SensorSeriesGroup(BaseModel):
    temperature: list[MetricSeriesPoint] = Field(default_factory=list)
    humidity: list[MetricSeriesPoint] = Field(default_factory=list)
    ec: list[MetricSeriesPoint] = Field(default_factory=list)
    ph: list[MetricSeriesPoint] = Field(default_factory=list)


class SensorSeriesResponse(BaseModel):
    range: str
    bucket: SensorBucket
    zone: str | None = None
    provider: str | None = None
    metrics: list[SensorMetric]
    timezone: str = "Asia/Shanghai"
    storageTimezone: str = "UTC"
    series: SensorSeriesGroup = Field(default_factory=SensorSeriesGroup)


class MetricSummary(BaseModel):
    latest: float
    latestAtUtc: datetime
    latestAtLocal: datetime
    avg: float
    min: float
    max: float
    sampleCount: int


class MetricSummaryGroup(BaseModel):
    temperature: MetricSummary | None = None
    humidity: MetricSummary | None = None
    ec: MetricSummary | None = None
    ph: MetricSummary | None = None


class SensorDashboardMeta(BaseModel):
    range: SensorRange
    bucket: SensorBucket
    zone: str | None = None
    provider: str | None = None
    timezone: str = "Asia/Shanghai"
    storageTimezone: str = "UTC"


class SensorDashboardResponse(BaseModel):
    summary: MetricSummaryGroup = Field(default_factory=MetricSummaryGroup)
    series: SensorSeriesGroup = Field(default_factory=SensorSeriesGroup)
    meta: SensorDashboardMeta
