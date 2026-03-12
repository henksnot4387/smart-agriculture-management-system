from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.ai.copilot.deepseek import DeepSeekClient
from app.ai.copilot.fallback import RuleBasedFallbackGenerator
from app.ai.copilot.types import RecommendationDraft, RecommendationGenerationResult
from app.ai.summary.service import CopilotSummaryService
from app.core.config import Settings
from app.repositories.knowledge import LocalKnowledgeRepository
from app.repositories.task import TaskRepository
from app.schemas.copilot import (
    CopilotRecommendationGenerateResponse,
    CopilotRecommendationItem,
    CopilotRecommendationListResponse,
    RecommendationTaskStatus,
)


class CopilotRecommendationService:
    def __init__(
        self,
        *,
        settings: Settings,
        summary_service: CopilotSummaryService,
        knowledge_repository: LocalKnowledgeRepository,
        task_repository: TaskRepository,
        deepseek_client: DeepSeekClient,
        fallback_generator: RuleBasedFallbackGenerator,
    ):
        self._settings = settings
        self._summary_service = summary_service
        self._knowledge_repository = knowledge_repository
        self._task_repository = task_repository
        self._deepseek_client = deepseek_client
        self._fallback_generator = fallback_generator

    def generate_and_persist(
        self,
        *,
        created_by_id: str,
        hours: int,
        zone: str | None,
        provider: str | None,
        instruction: str | None,
        max_items: int | None,
    ) -> CopilotRecommendationGenerateResponse:
        bounded_hours = max(1, min(hours, 168))
        resolved_max_items = max(1, min(max_items or self._settings.copilot_recommendation_max_items, 10))
        summary = self._summary_service.get_summary(
            hours=bounded_hours,
            zone=zone,
            provider=provider,
        )
        knowledge_refs = self._select_knowledge_refs(
            summary_narrative=summary.narrative,
            disease_terms=[item.diseaseType for item in summary.diseaseCounts[:8]],
            instruction=instruction,
            limit=8,
        )

        generation = self._generate_with_fallback(
            summary=summary,
            instruction=instruction,
            knowledge_refs=knowledge_refs,
            max_items=resolved_max_items,
        )
        records: list[CopilotRecommendationItem] = []
        generated_at = datetime.now(UTC)
        for draft in generation.recommendations[:resolved_max_items]:
            task_row = self._task_repository.create_ai_task(
                title=draft.title,
                description=draft.description,
                priority=draft.priority,
                created_by_id=created_by_id,
                due_at=generated_at + timedelta(hours=draft.due_hours),
                metadata=self._build_task_metadata(
                    summary_hours=bounded_hours,
                    zone=zone,
                    provider=summary.provider,
                    instruction=instruction,
                    draft=draft,
                    generation=generation,
                    knowledge_refs=knowledge_refs,
                ),
            )
            records.append(self._row_to_recommendation_item(task_row))

        return CopilotRecommendationGenerateResponse(
            generatedAtUtc=generated_at,
            hours=bounded_hours,
            zone=zone,
            provider=summary.provider,
            llmProvider=generation.provider,
            llmModel=generation.model,
            fallbackUsed=generation.fallback_used,
            recommendations=records,
        )

    def list_recommendations(
        self,
        *,
        limit: int,
        status: RecommendationTaskStatus | None,
    ) -> CopilotRecommendationListResponse:
        bounded_limit = max(1, min(limit, 100))
        total, rows = self._task_repository.list_ai_tasks(limit=bounded_limit, status=status)
        items = [self._row_to_recommendation_item(row) for row in rows]
        return CopilotRecommendationListResponse(
            total=total,
            limit=bounded_limit,
            status=status,
            items=items,
        )

    def _generate_with_fallback(
        self,
        *,
        summary,
        instruction: str | None,
        knowledge_refs: list[dict[str, Any]],
        max_items: int,
    ) -> RecommendationGenerationResult:
        try:
            if self._deepseek_client.enabled:
                return self._deepseek_client.generate(
                    summary=summary,
                    instruction=instruction,
                    knowledge_refs=knowledge_refs,
                    max_items=max_items,
                )
        except Exception:  # noqa: BLE001
            pass
        return self._fallback_generator.generate(
            summary=summary,
            instruction=instruction,
            max_items=max_items,
        )

    def _build_task_metadata(
        self,
        *,
        summary_hours: int,
        zone: str | None,
        provider: str | None,
        instruction: str | None,
        draft: RecommendationDraft,
        generation: RecommendationGenerationResult,
        knowledge_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        refs = [str(item.get("id")) for item in knowledge_refs[:8] if item.get("id")]
        return {
            "copilot": {
                "reason": draft.reason,
                "suggestedRole": draft.suggested_role,
                "dueHours": draft.due_hours,
                "instruction": instruction.strip() if instruction else None,
                "windowHours": summary_hours,
                "zone": zone,
                "provider": provider,
                "knowledgeRefs": refs,
                "llm": {
                    "provider": generation.provider,
                    "model": generation.model,
                    "requestId": generation.request_id,
                    "fallbackUsed": generation.fallback_used,
                },
            }
        }

    def _row_to_recommendation_item(self, row: dict[str, Any]) -> CopilotRecommendationItem:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        copilot = metadata.get("copilot") if isinstance(metadata.get("copilot"), dict) else {}
        llm = copilot.get("llm") if isinstance(copilot.get("llm"), dict) else {}
        return CopilotRecommendationItem(
            taskId=str(row["id"]),
            title=str(row.get("title") or ""),
            description=str(row.get("description") or ""),
            reason=str(copilot.get("reason") or ""),
            priority=str(row.get("priority") or "MEDIUM"),
            suggestedRole=str(copilot.get("suggestedRole") or "WORKER"),
            dueHours=int(copilot.get("dueHours") or 24),
            status=str(row.get("status") or "PENDING"),
            createdAt=row["created_at"],
            llmProvider=str(llm.get("provider") or "fallback"),
            llmModel=str(llm.get("model") or "") or None,
            fallbackUsed=bool(llm.get("fallbackUsed", False)),
            knowledgeRefs=[str(item) for item in copilot.get("knowledgeRefs") or []],
        )

    def _select_knowledge_refs(
        self,
        *,
        summary_narrative: str,
        disease_terms: list[str],
        instruction: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        doc = self._knowledge_repository.get_document()
        items = [item for item in doc.get("items", []) if isinstance(item, dict)]

        seed_tokens = self._extract_tokens(summary_narrative)
        if instruction:
            seed_tokens.extend(self._extract_tokens(instruction))
        for term in disease_terms:
            seed_tokens.extend(self._extract_tokens(term))

        dedup_tokens = []
        seen: set[str] = set()
        for token in seed_tokens:
            if token in seen:
                continue
            seen.add(token)
            dedup_tokens.append(token)
        if not dedup_tokens:
            return items[:limit]

        scored: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            haystack = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("whyImportant") or ""),
                    " ".join(str(kw) for kw in item.get("keywords", [])),
                ]
            ).lower()
            score = 0
            for token in dedup_tokens[:30]:
                if token and token in haystack:
                    score += 1
            if score > 0:
                scored.append((score, item))

        scored.sort(
            key=lambda pair: (
                pair[0],
                str(pair[1].get("updatedAt") or ""),
            ),
            reverse=True,
        )
        if scored:
            return [item for _, item in scored[:limit]]
        return items[:limit]

    def _extract_tokens(self, text: str) -> list[str]:
        candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text or "")
        return [item.lower() for item in candidates if len(item) >= 2]
