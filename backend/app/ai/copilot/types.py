from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RecommendationPriority = Literal["LOW", "MEDIUM", "HIGH"]
RecommendationSuggestedRole = Literal["SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"]


@dataclass(slots=True)
class RecommendationDraft:
    title: str
    description: str
    reason: str
    priority: RecommendationPriority = "MEDIUM"
    suggested_role: RecommendationSuggestedRole = "WORKER"
    due_hours: int = 24


@dataclass(slots=True)
class RecommendationGenerationResult:
    provider: str
    model: str | None
    fallback_used: bool
    request_id: str | None
    recommendations: list[RecommendationDraft] = field(default_factory=list)
