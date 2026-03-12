from __future__ import annotations

from app.repositories.knowledge import LocalKnowledgeRepository
from app.schemas.knowledge import KnowledgeListResponse, KnowledgeMetaResponse


class KnowledgeService:
    def __init__(self, repository: LocalKnowledgeRepository):
        self._repository = repository

    def list_knowledge(
        self,
        *,
        category_id: str | None,
        query: str | None,
        keywords: list[str],
        limit: int,
    ) -> KnowledgeListResponse:
        total, items = self._repository.list_items(
            category_id=category_id,
            query=query,
            keywords=keywords,
            limit=limit,
        )
        return KnowledgeListResponse(total=total, items=items)

    def get_meta(self) -> KnowledgeMetaResponse:
        return KnowledgeMetaResponse(**self._repository.get_meta())
