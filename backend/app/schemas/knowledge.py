from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeCategory(BaseModel):
    id: str
    name: str
    description: str


class KnowledgeSource(BaseModel):
    title: str
    url: str
    type: str | None = None
    publisher: str | None = None
    publishedAt: str | None = None
    fetchedAt: datetime | None = None


class KnowledgeItem(BaseModel):
    id: str
    categoryId: str
    categoryName: str
    title: str
    summary: str
    whyImportant: str | None = None
    actionablePoints: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    source: KnowledgeSource
    lastAttemptAt: datetime | None = None
    fetchStatus: str | None = None
    lastError: str | None = None
    updatedAt: datetime | None = None


class KnowledgeListResponse(BaseModel):
    total: int
    items: list[KnowledgeItem]


class KnowledgeMetaResponse(BaseModel):
    version: str
    generatedAt: datetime
    seedKeywords: list[str]
    categories: list[KnowledgeCategory]
    topKeywords: list[str]
    harvestLastRunAt: datetime | None = None
    harvestAttempted: int = 0
    harvestSucceeded: int = 0
    harvestFailed: int = 0
    harvestSuccessRate: float = 0
