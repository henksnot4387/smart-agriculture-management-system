from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RecommendationTaskStatus = Literal["PENDING", "APPROVED", "IN_PROGRESS", "COMPLETED"]
RecommendationPriority = Literal["LOW", "MEDIUM", "HIGH"]
RecommendationSuggestedRole = Literal["SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"]
AIInsightFreshnessStatus = Literal["FRESH", "WARNING", "STALE"]
AIInsightSummaryMode = Literal["cached", "refresh"]
AIInsightDraftStatus = Literal["PENDING", "CONFIRMED"]


class AIInsightDataEvidence(BaseModel):
    label: str
    value: str


class AIInsightKnowledgeEvidence(BaseModel):
    id: str
    title: str
    summary: str
    sourceUrl: str | None = None


class AIInsightExecutive(BaseModel):
    headline: str
    riskLevel: Literal["LOW", "MEDIUM", "HIGH"]
    keyFindings: list[str] = Field(default_factory=list)


class AIInsightExpertItem(BaseModel):
    title: str
    problem: str
    cause: str
    action: str
    priority: RecommendationPriority
    dataEvidence: list[AIInsightDataEvidence] = Field(default_factory=list)
    knowledgeEvidence: list[AIInsightKnowledgeEvidence] = Field(default_factory=list)


class AIInsightZoneRiskItem(BaseModel):
    zone: str
    riskScore: float
    anomalyMinutes: float
    anomalousSamples: int


class AIInsightTrendPoint(BaseModel):
    metric: Literal["temperature", "humidity", "ec", "ph"]
    bucketStartUtc: datetime
    bucketStartLocal: str
    avg: float
    min: float
    max: float
    count: int


class AIInsightAnomalyTimelineItem(BaseModel):
    metric: Literal["temperature", "humidity", "ec", "ph"]
    anomalyDurationMinutes: float
    anomalousSamples: int


class AIInsightVisual(BaseModel):
    zoneRisks: list[AIInsightZoneRiskItem] = Field(default_factory=list)
    trends: list[AIInsightTrendPoint] = Field(default_factory=list)
    anomalyTimeline: list[AIInsightAnomalyTimelineItem] = Field(default_factory=list)


class AIInsightDraftItem(BaseModel):
    draftId: str
    title: str
    description: str
    reason: str
    priority: RecommendationPriority
    suggestedRole: RecommendationSuggestedRole
    dueHours: int
    status: AIInsightDraftStatus
    llmProvider: str
    llmModel: str | None = None
    fallbackUsed: bool
    knowledgeRefs: list[str] = Field(default_factory=list)
    dataEvidence: list[AIInsightDataEvidence] = Field(default_factory=list)
    knowledgeEvidence: list[AIInsightKnowledgeEvidence] = Field(default_factory=list)
    createdAt: datetime
    confirmedAt: datetime | None = None
    taskId: str | None = None


class AIInsightSummaryMeta(BaseModel):
    source: str
    freshnessStatus: AIInsightFreshnessStatus
    pageRefreshedAt: datetime
    latestSampleAtUtc: datetime | None = None
    latestSampleAtLocal: str | None = None
    timezone: str = "Asia/Shanghai"
    storageTimezone: str = "UTC"
    engineProvider: str
    engineModel: str | None = None
    fallbackUsed: bool = False
    warningMessage: str | None = None


class AIInsightSummaryResponse(BaseModel):
    meta: AIInsightSummaryMeta
    executive: AIInsightExecutive
    expert: list[AIInsightExpertItem] = Field(default_factory=list)
    visual: AIInsightVisual
    recommendationDrafts: list[AIInsightDraftItem] = Field(default_factory=list)


class AIInsightRecommendationGenerateRequest(BaseModel):
    hours: int = Field(default=24, ge=1, le=168)
    zone: str | None = None
    provider: str | None = None
    instruction: str | None = None
    maxItems: int | None = Field(default=None, ge=1, le=10)


class AIInsightRecommendationGenerateResponse(BaseModel):
    generatedAtUtc: datetime
    hours: int
    zone: str | None = None
    provider: str | None = None
    llmProvider: str
    llmModel: str | None = None
    fallbackUsed: bool
    recommendations: list[AIInsightDraftItem]


class AIInsightRecommendationListResponse(BaseModel):
    total: int
    limit: int
    status: AIInsightDraftStatus | None = None
    items: list[AIInsightDraftItem]


class AIInsightRecommendationConfirmRequest(BaseModel):
    draftIds: list[str] = Field(min_length=1, max_length=20)


class AIInsightConfirmedTask(BaseModel):
    draftId: str
    taskId: str
    title: str
    status: RecommendationTaskStatus
    priority: RecommendationPriority
    createdAt: datetime


class AIInsightRecommendationConfirmResponse(BaseModel):
    confirmedAtUtc: datetime
    confirmedCount: int
    tasks: list[AIInsightConfirmedTask]
