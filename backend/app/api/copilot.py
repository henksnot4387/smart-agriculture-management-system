from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.auth_context import ActorContext, require_actor, require_roles
from app.ai.copilot.dependencies import get_ai_insights_service
from app.ai.copilot.ai_insights_service import AIInsightsService
from app.core.security import require_api_token
from app.repositories.knowledge import LocalKnowledgeRepository
from app.schemas.ai_insights import (
    AIInsightRecommendationConfirmRequest,
    AIInsightRecommendationConfirmResponse,
    AIInsightRecommendationGenerateRequest,
    AIInsightRecommendationGenerateResponse,
    AIInsightRecommendationListResponse,
    AIInsightSummaryResponse,
)
from app.schemas.knowledge import KnowledgeListResponse, KnowledgeMetaResponse
from app.services.knowledge import KnowledgeService

router = APIRouter(
    prefix="/api/ai-insights",
    tags=["ai-insights"],
    dependencies=[Depends(require_api_token)],
)

legacy_router = APIRouter(
    prefix="/api/copilot",
    tags=["copilot-legacy"],
    dependencies=[Depends(require_api_token)],
)

require_ai_manage_role = require_roles({"SUPER_ADMIN", "ADMIN", "EXPERT"})


def _mark_deprecated_header(request: Request, response: Response) -> None:
    if request.url.path.startswith("/api/copilot"):
        response.headers["Deprecation"] = "true"
        response.headers["X-API-Deprecated"] = "Use /api/ai-insights/*"


@lru_cache
def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService(repository=LocalKnowledgeRepository())


@router.get("/summary", response_model=AIInsightSummaryResponse)
@legacy_router.get("/summary", response_model=AIInsightSummaryResponse)
def get_ai_insights_summary(
    request: Request,
    response: Response,
    hours: int = Query(default=24, ge=1, le=168),
    zone: str | None = Query(default=None),
    mode: str = Query(default="cached", pattern="^(cached|refresh)$"),
    provider: str | None = None,
    _: ActorContext = Depends(require_actor),
    service: AIInsightsService = Depends(get_ai_insights_service),
) -> AIInsightSummaryResponse:
    _mark_deprecated_header(request, response)
    return service.get_summary(
        hours=hours,
        zone=zone,
        mode=mode,
        provider=provider,
    )


@router.get("/knowledge", response_model=KnowledgeListResponse)
@legacy_router.get("/knowledge", response_model=KnowledgeListResponse)
def list_knowledge(
    request: Request,
    response: Response,
    category: str | None = None,
    q: str | None = None,
    keywords: str | None = None,
    limit: int = Query(default=30, ge=1, le=200),
    _: ActorContext = Depends(require_actor),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeListResponse:
    _mark_deprecated_header(request, response)
    parsed_keywords = [keyword.strip() for keyword in (keywords or "").split(",") if keyword.strip()]
    return service.list_knowledge(
        category_id=category,
        query=q,
        keywords=parsed_keywords,
        limit=limit,
    )


@router.get("/knowledge/meta", response_model=KnowledgeMetaResponse)
@legacy_router.get("/knowledge/meta", response_model=KnowledgeMetaResponse)
def get_knowledge_meta(
    request: Request,
    response: Response,
    _: ActorContext = Depends(require_actor),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeMetaResponse:
    _mark_deprecated_header(request, response)
    return service.get_meta()


@router.post("/recommendations", response_model=AIInsightRecommendationGenerateResponse)
@legacy_router.post("/recommendations", response_model=AIInsightRecommendationGenerateResponse)
def generate_ai_recommendations(
    request: Request,
    response: Response,
    payload: AIInsightRecommendationGenerateRequest,
    _: ActorContext = Depends(require_ai_manage_role),
    service: AIInsightsService = Depends(get_ai_insights_service),
) -> AIInsightRecommendationGenerateResponse:
    _mark_deprecated_header(request, response)
    try:
        return service.generate_recommendations(
            hours=payload.hours,
            zone=payload.zone,
            provider=payload.provider,
            instruction=payload.instruction,
            max_items=payload.maxItems,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate recommendations: {exc}",
        ) from exc


@router.get("/recommendations", response_model=AIInsightRecommendationListResponse)
@legacy_router.get("/recommendations", response_model=AIInsightRecommendationListResponse)
def list_ai_recommendations(
    request: Request,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default="PENDING", alias="status"),
    _: ActorContext = Depends(require_actor),
    service: AIInsightsService = Depends(get_ai_insights_service),
) -> AIInsightRecommendationListResponse:
    _mark_deprecated_header(request, response)
    return service.list_recommendations(limit=limit, status=status_filter)


@router.post("/recommendations/confirm", response_model=AIInsightRecommendationConfirmResponse)
@legacy_router.post("/recommendations/confirm", response_model=AIInsightRecommendationConfirmResponse)
def confirm_ai_recommendations(
    request: Request,
    response: Response,
    payload: AIInsightRecommendationConfirmRequest,
    actor: ActorContext = Depends(require_ai_manage_role),
    service: AIInsightsService = Depends(get_ai_insights_service),
) -> AIInsightRecommendationConfirmResponse:
    _mark_deprecated_header(request, response)
    try:
        return service.confirm_recommendations(
            draft_ids=payload.draftIds,
            confirmed_by_id=actor.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
