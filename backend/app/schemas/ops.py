from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OpsValueType = Literal["numeric", "status", "percentage"]


class MetricCatalogItem(BaseModel):
    controlTypeId: str
    parameterId: str
    controlTypeName: str
    parameterName: str
    metricKey: str
    displayName: str
    module: str
    moduleLabel: str
    area: str
    valueType: str
    unit: str
    canonicalMetric: str | None = None
    covered: bool
    latestSampleAtUtc: datetime | None = None
    latestSampleAtLocal: str | None = None


class OpsCatalogCoverage(BaseModel):
    total: int
    covered: int
    coverageRate: float
    gatePassed: bool


class OpsCatalogResponse(BaseModel):
    version: str
    source: str
    systemId: str
    provider: str
    coverage: OpsCatalogCoverage
    items: list[MetricCatalogItem] = Field(default_factory=list)


class OpsMetricValue(BaseModel):
    metricKey: str
    displayName: str
    value: float
    unit: str
    valueType: str
    module: str
    moduleLabel: str
    area: str
    recordedAtUtc: datetime
    recordedAtLocal: str


class OpsZoneSnapshot(BaseModel):
    zone: str
    latestSampleAtUtc: datetime | None = None
    latestSampleAtLocal: str | None = None
    metrics: list[OpsMetricValue] = Field(default_factory=list)


class OpsModuleSnapshot(BaseModel):
    module: str
    moduleLabel: str
    zoneCount: int
    metricCount: int


class OpsLiveMeta(BaseModel):
    provider: str
    lookbackHours: int
    pageRefreshedAt: datetime
    latestSampleAtUtc: datetime | None = None
    latestSampleAtLocal: str | None = None
    freshnessStatus: Literal["FRESH", "WARNING", "STALE"]
    warningMessage: str | None = None
    timezone: str = "Asia/Shanghai"
    storageTimezone: str = "UTC"


class OpsLiveResponse(BaseModel):
    meta: OpsLiveMeta
    zones: list[OpsZoneSnapshot] = Field(default_factory=list)
    modules: list[OpsModuleSnapshot] = Field(default_factory=list)


class OpsTrendPoint(BaseModel):
    metricKey: str
    displayName: str
    module: str
    moduleLabel: str
    bucketStartUtc: datetime
    bucketStartLocal: str
    avg: float
    min: float
    max: float
    count: int


class OpsTrendsResponse(BaseModel):
    provider: str
    startUtc: datetime
    endUtc: datetime
    zone: str | None = None
    points: list[OpsTrendPoint] = Field(default_factory=list)
