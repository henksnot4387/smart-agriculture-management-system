from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ObservabilityRouteMetric(BaseModel):
    route: str
    requestCount: int
    errorCount: int
    slowCount: int
    avgLatencyMs: float
    p95LatencyMs: float
    maxLatencyMs: float


class ObservabilityDomainMetric(BaseModel):
    domain: str
    requestCount: int
    errorCount: int
    slowCount: int


class ObservabilityErrorCodeMetric(BaseModel):
    errorCode: str
    count: int


class ObservabilityErrorEvent(BaseModel):
    requestId: str
    method: str
    path: str
    route: str
    statusCode: int
    durationMs: float
    errorCode: str | None = None
    userId: str | None = None
    userRole: str | None = None
    occurredAt: datetime


class ObservabilityTaskFailureMetric(BaseModel):
    jobId: str
    failedCount: int
    lastFailedAt: datetime | None = None
    lastError: str | None = None


class ObservabilityOverviewResponse(BaseModel):
    windowHours: int
    slowThresholdMs: int
    totalRequests: int
    errorRequests: int
    slowRequests: int
    p95LatencyMs: float
    topRoutes: list[ObservabilityRouteMetric] = Field(default_factory=list)
    domainStats: list[ObservabilityDomainMetric] = Field(default_factory=list)
    errorCodeStats: list[ObservabilityErrorCodeMetric] = Field(default_factory=list)
    taskFailures: list[ObservabilityTaskFailureMetric] = Field(default_factory=list)


class ObservabilityErrorsResponse(BaseModel):
    windowHours: int
    items: list[ObservabilityErrorEvent] = Field(default_factory=list)


class ObservabilitySlowRequestsResponse(BaseModel):
    windowHours: int
    slowThresholdMs: int
    items: list[ObservabilityErrorEvent] = Field(default_factory=list)


class ObservabilityTaskFailuresResponse(BaseModel):
    windowHours: int
    items: list[ObservabilityTaskFailureMetric] = Field(default_factory=list)
