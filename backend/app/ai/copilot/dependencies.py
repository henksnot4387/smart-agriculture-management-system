from __future__ import annotations

from functools import lru_cache

from app.ai.copilot.ai_insights_service import AIInsightsService
from app.ai.copilot.deepseek import DeepSeekClient
from app.ai.copilot.fallback import RuleBasedFallbackGenerator
from app.ai.copilot.service import CopilotRecommendationService
from app.ai.summary.service import CopilotSummaryService
from app.core.config import settings
from app.repositories.ai_insights import AIInsightsRepository
from app.repositories.knowledge import LocalKnowledgeRepository
from app.repositories.summary import CopilotSummaryRepository
from app.repositories.task import TaskRepository


@lru_cache
def get_copilot_recommendation_service() -> CopilotRecommendationService:
    summary_service = CopilotSummaryService(
        settings=settings,
        repository=CopilotSummaryRepository(settings),
    )
    return CopilotRecommendationService(
        settings=settings,
        summary_service=summary_service,
        knowledge_repository=LocalKnowledgeRepository(),
        task_repository=TaskRepository(settings),
        deepseek_client=DeepSeekClient(settings),
        fallback_generator=RuleBasedFallbackGenerator(),
    )


@lru_cache
def get_ai_insights_service() -> AIInsightsService:
    return AIInsightsService(
        settings=settings,
        repository=AIInsightsRepository(settings),
        knowledge_repository=LocalKnowledgeRepository(),
    )
