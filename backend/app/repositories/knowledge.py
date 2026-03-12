from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.core.config import REPO_ROOT


class LocalKnowledgeRepository:
    def __init__(self, knowledge_file: Path | None = None):
        self._knowledge_file = knowledge_file or (REPO_ROOT / "backend" / "data" / "knowledge_base.json")
        self._cache: dict[str, Any] | None = None
        self._cache_mtime: float | None = None

    def get_document(self) -> dict[str, Any]:
        if not self._knowledge_file.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Knowledge base file not found: {self._knowledge_file}",
            )

        mtime = self._knowledge_file.stat().st_mtime
        if self._cache is not None and self._cache_mtime == mtime:
            return self._cache

        self._cache = json.loads(self._knowledge_file.read_text(encoding="utf-8"))
        self._cache_mtime = mtime
        return self._cache

    def list_items(
        self,
        *,
        category_id: str | None,
        query: str | None,
        keywords: list[str],
        limit: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        doc = self.get_document()
        items = list(doc.get("items", []))
        categories = {item["id"]: item["name"] for item in doc.get("categories", [])}

        filtered: list[dict[str, Any]] = []
        query_terms = [term.strip().lower() for term in (query or "").split(" ") if term.strip()]
        keyword_terms = [kw.strip().lower() for kw in keywords if kw.strip()]

        for item in items:
            if category_id and item.get("categoryId") != category_id:
                continue

            item_keywords = [str(keyword).lower() for keyword in item.get("keywords", [])]
            item_text = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("summary", "")),
                    str(item.get("whyImportant", "")),
                    " ".join(item_keywords),
                ]
            ).lower()

            if query_terms and not all(term in item_text for term in query_terms):
                continue
            if keyword_terms and not all(term in item_keywords for term in keyword_terms):
                continue

            filtered.append(
                {
                    **item,
                    "categoryName": categories.get(item.get("categoryId"), item.get("categoryId", "未分类")),
                }
            )

        filtered.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        total = len(filtered)
        return total, filtered[:limit]

    def get_meta(self) -> dict[str, Any]:
        doc = self.get_document()
        categories = list(doc.get("categories", []))
        seed_keywords = list(doc.get("seedKeywords", []))
        items = list(doc.get("items", []))
        harvest = dict(doc.get("harvest", {}))
        keyword_counter: dict[str, int] = {}
        for item in items:
            for keyword in item.get("keywords", []):
                normalized = str(keyword).strip().lower()
                if not normalized:
                    continue
                keyword_counter[normalized] = keyword_counter.get(normalized, 0) + 1
        top_keywords = [key for key, _ in sorted(keyword_counter.items(), key=lambda kv: kv[1], reverse=True)[:40]]

        return {
            "version": str(doc.get("version", "v1")),
            "generatedAt": doc.get("generatedAt"),
            "seedKeywords": seed_keywords,
            "categories": categories,
            "topKeywords": top_keywords,
            "harvestLastRunAt": harvest.get("lastRunAt"),
            "harvestAttempted": int(harvest.get("attempted", 0) or 0),
            "harvestSucceeded": int(harvest.get("succeeded", 0) or 0),
            "harvestFailed": int(harvest.get("failed", 0) or 0),
            "harvestSuccessRate": float(harvest.get("successRate", 0) or 0),
        }
