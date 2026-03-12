from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


VisionTaskStatus = Literal["PROCESSING", "DONE", "FAILED"]


class VisionDetectionBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class VisionDetectionItem(BaseModel):
    label: str
    confidence: float
    bbox: VisionDetectionBox | None = None


class VisionTaskResponse(BaseModel):
    taskId: str
    status: VisionTaskStatus
    source: str
    imageUrl: str
    diseaseType: str | None = None
    confidence: float | None = None
    detections: list[VisionDetectionItem] = Field(default_factory=list)
    engine: str | None = None
    device: str | None = None
    fallbackOccurred: bool | None = None
    error: str | None = None
    queuedAt: datetime | None = None
    processedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class VisionTaskListResponse(BaseModel):
    items: list[VisionTaskResponse]


class VisionRuntimeResponse(BaseModel):
    mode: str
    engine: str
    preferredDevice: str
    activeDevice: str
    fallbackOccurred: bool
    storageBackend: str
    queueKey: str
    queueDepth: int
    maxUploadMb: int
