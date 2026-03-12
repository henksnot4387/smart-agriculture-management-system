from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceBox:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class InferenceDetection:
    label: str
    confidence: float
    bbox: InferenceBox | None = None


@dataclass(frozen=True)
class InferenceResult:
    detections: list[InferenceDetection]
    engine: str
    device: str
    fallback_occurred: bool
