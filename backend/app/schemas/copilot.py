from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SummaryMetricKey = Literal["temperature", "humidity", "ec", "ph"]
RecommendationTaskStatus = Literal["PENDING", "APPROVED", "IN_PROGRESS", "COMPLETED"]
RecommendationPriority = Literal["LOW", "MEDIUM", "HIGH"]
RecommendationSuggestedRole = Literal["SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"]


class SummaryMetricStats(BaseModel):
    latest: float | None = None
    avg: float | None = None
    min: float | None = None
    max: float | None = None
    sampleCount: int = 0
    lowThreshold: float
    highThreshold: float
    anomalousSamples: int = 0
    anomalyDurationMinutes: float = 0


class SummaryMetricGroup(BaseModel):
    temperature: SummaryMetricStats
    humidity: SummaryMetricStats
    ec: SummaryMetricStats
    ph: SummaryMetricStats


class DiseaseCountItem(BaseModel):
    diseaseType: str
    count: int


class CopilotSummaryResponse(BaseModel):
    windowStartUtc: datetime
    windowEndUtc: datetime
    generatedAtUtc: datetime
    hours: int
    provider: str | None = None
    zone: str | None = None
    metrics: SummaryMetricGroup
    diseaseCounts: list[DiseaseCountItem]
    totalDiseaseEvents: int
    narrative: str


class CopilotRecommendationGenerateRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=168)
    zone: str | None = None
    provider: str | None = None
    instruction: str | None = None
    maxItems: int | None = Field(default=None, ge=1, le=10)


class CopilotRecommendationItem(BaseModel):
    taskId: str
    title: str
    description: str
    reason: str
    priority: RecommendationPriority
    suggestedRole: RecommendationSuggestedRole
    dueHours: int
    status: RecommendationTaskStatus
    createdAt: datetime
    llmProvider: str
    llmModel: str | None = None
    fallbackUsed: bool = False
    knowledgeRefs: list[str] = Field(default_factory=list)


class CopilotRecommendationGenerateResponse(BaseModel):
    generatedAtUtc: datetime
    hours: int
    zone: str | None = None
    provider: str | None = None
    llmProvider: str
    llmModel: str | None = None
    fallbackUsed: bool
    recommendations: list[CopilotRecommendationItem]


class CopilotRecommendationListResponse(BaseModel):
    total: int
    limit: int
    status: RecommendationTaskStatus | None = None
    items: list[CopilotRecommendationItem]
