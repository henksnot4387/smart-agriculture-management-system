from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from datetime import timedelta
import logging
import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from psycopg import errors as psycopg_errors
from redis import Redis

from app.ai.vision.events import VisionTaskEventHub
from app.ai.vision.inference import VisionInferenceEngine
from app.ai.vision.storage import StorageService
from app.core.config import Settings
from app.repositories.vision import VisionTaskRepository
from app.schemas.vision import (
    VisionDetectionBox,
    VisionDetectionItem,
    VisionRuntimeResponse,
    VisionTaskListResponse,
    VisionTaskResponse,
)

logger = logging.getLogger("app.ai.vision.service")

ALLOWED_SOURCES = {"CAMERA", "DRONE", "MOBILE"}


class VisionTaskService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: VisionTaskRepository,
        storage: StorageService,
        inference: VisionInferenceEngine,
        redis_client: Redis,
        event_hub: VisionTaskEventHub | None = None,
    ):
        self._settings = settings
        self._repository = repository
        self._storage = storage
        self._inference = inference
        self._redis = redis_client
        self._event_hub = event_hub

    @property
    def storage_backend(self) -> str:
        return self._storage.backend_name

    @property
    def storage_root_path(self) -> Path | None:
        root_path = getattr(self._storage, "root_path", None)
        if isinstance(root_path, Path):
            return root_path
        return None

    async def submit_task(
        self,
        *,
        file_name: str | None,
        content_type: str | None,
        file_bytes: bytes,
        source: str = "MOBILE",
        uploaded_by_id: str | None = None,
    ) -> VisionTaskResponse:
        if source not in ALLOWED_SOURCES:
            source = "MOBILE"

        max_bytes = self._settings.vision_max_upload_mb * 1024 * 1024
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")
        if len(file_bytes) > max_bytes:
            raise ValueError(f"Uploaded file exceeds {self._settings.vision_max_upload_mb} MB limit.")

        normalized_content_type = (content_type or "").strip().lower() or "application/octet-stream"
        if not normalized_content_type.startswith("image/"):
            raise ValueError("Only image uploads are supported.")

        task_id = str(uuid4())
        storage_key = self._build_storage_key(task_id, file_name=file_name, content_type=normalized_content_type)
        stored = await asyncio.to_thread(
            self._storage.save_bytes,
            storage_key,
            file_bytes,
            normalized_content_type,
        )

        raw_result = {
            "queued_at": datetime.now(UTC).isoformat(),
            "storageBackend": self._storage.backend_name,
            "storageKey": stored.key,
            "contentType": normalized_content_type,
            "sizeBytes": stored.size_bytes,
            "detections": [],
        }
        try:
            row = await asyncio.to_thread(
                self._repository.create_task,
                task_id=task_id,
                image_url=stored.public_url,
                source=source,
                uploaded_by_id=uploaded_by_id,
                captured_at=None,
                raw_result=raw_result,
            )
        except psycopg_errors.ForeignKeyViolation as exc:
            raise ValueError("X-User-Id does not exist in users table.") from exc
        except psycopg_errors.InvalidTextRepresentation as exc:
            raise ValueError("X-User-Id must be a valid UUID string.") from exc

        await asyncio.to_thread(self._redis.rpush, self._settings.vision_queue_key, task_id)
        response = self._build_task_response(row)
        await self._emit_task_event("vision.task.accepted", response)
        return response

    async def get_task(self, task_id: str) -> VisionTaskResponse | None:
        row = await asyncio.to_thread(self._repository.get_task, task_id)
        if not row:
            return None
        if self._is_processing_timeout(row):
            await asyncio.to_thread(
                self._repository.mark_failed,
                task_id=task_id,
                error_message="Task timed out in PROCESSING state.",
                raw_result=self._build_timeout_raw_result(row),
            )
            row = await asyncio.to_thread(self._repository.get_task, task_id)
            if not row:
                return None
        return self._build_task_response(row)

    async def list_tasks(self, limit: int = 20) -> VisionTaskListResponse:
        bounded_limit = max(1, min(limit, 100))
        rows = await asyncio.to_thread(self._repository.list_recent, bounded_limit)
        timeout_ids = [str(row["id"]) for row in rows if self._is_processing_timeout(row)]
        if timeout_ids:
            for task_id in timeout_ids:
                timeout_row = next((row for row in rows if str(row["id"]) == task_id), None)
                if timeout_row is None:
                    continue
                await asyncio.to_thread(
                    self._repository.mark_failed,
                    task_id=task_id,
                    error_message="Task timed out in PROCESSING state.",
                    raw_result=self._build_timeout_raw_result(timeout_row),
                )
            rows = await asyncio.to_thread(self._repository.list_recent, bounded_limit)
        return VisionTaskListResponse(items=[self._build_task_response(row) for row in rows])

    async def process_next_task(self, timeout_seconds: int = 1) -> bool:
        item = await asyncio.to_thread(self._redis.blpop, self._settings.vision_queue_key, timeout_seconds)
        if not item:
            return False

        _, task_id = item
        if isinstance(task_id, bytes):
            task_id = task_id.decode("utf-8")
        normalized_task_id = str(task_id)
        await asyncio.to_thread(self._process_task_sync, normalized_task_id)
        updated_row = await asyncio.to_thread(self._repository.get_task, normalized_task_id)
        if updated_row:
            await self._emit_task_event("vision.task.updated", self._build_task_response(updated_row))
        return True

    async def get_runtime(self) -> VisionRuntimeResponse:
        runtime = self._inference.runtime_status()
        queue_depth = await self.get_queue_depth()
        return VisionRuntimeResponse(
            mode=str(runtime.get("mode", self._settings.vision_inference_mode)),
            engine=str(runtime.get("engine", "unknown")),
            preferredDevice=str(runtime.get("preferredDevice", "cpu")),
            activeDevice=str(runtime.get("activeDevice", "cpu")),
            fallbackOccurred=bool(runtime.get("fallbackOccurred", False)),
            storageBackend=self._storage.backend_name,
            queueKey=self._settings.vision_queue_key,
            queueDepth=queue_depth,
            maxUploadMb=self._settings.vision_max_upload_mb,
        )

    async def get_queue_depth(self) -> int:
        depth = await asyncio.to_thread(self._redis.llen, self._settings.vision_queue_key)
        return int(depth)

    def _build_storage_key(self, task_id: str, *, file_name: str | None, content_type: str) -> str:
        suffix = self._resolve_extension(file_name=file_name, content_type=content_type)
        date_prefix = datetime.now(UTC).strftime("%Y/%m/%d")
        return f"vision/original/{date_prefix}/{task_id}{suffix}"

    def _resolve_extension(self, *, file_name: str | None, content_type: str) -> str:
        if file_name:
            ext = Path(file_name).suffix.strip()
            if ext:
                return ext.lower()
        guessed = mimetypes.guess_extension(content_type)
        if guessed:
            return guessed
        return ".bin"

    def _process_task_sync(self, task_id: str) -> None:
        row = self._repository.get_task(task_id)
        if not row:
            logger.warning("Vision task not found while processing", extra={"task_id": task_id})
            return

        raw_result = row.get("raw_result") or {}
        storage_key = raw_result.get("storageKey")
        if not storage_key:
            self._repository.mark_failed(
                task_id=task_id,
                error_message="Missing storage key.",
                raw_result={**raw_result, "processed_at": datetime.now(UTC).isoformat()},
            )
            return

        try:
            image_bytes = self._storage.read_bytes(str(storage_key))
            inference_result = self._inference.infer(image_bytes)
            sorted_detections = sorted(
                inference_result.detections,
                key=lambda item: item.confidence,
                reverse=True,
            )
            top = sorted_detections[0] if sorted_detections else None
            detections_payload = [
                {
                    "label": detection.label,
                    "confidence": round(detection.confidence, 6),
                    "bbox": (
                        {
                            "x1": detection.bbox.x1,
                            "y1": detection.bbox.y1,
                            "x2": detection.bbox.x2,
                            "y2": detection.bbox.y2,
                        }
                        if detection.bbox
                        else None
                    ),
                }
                for detection in sorted_detections
            ]
            final_raw = {
                **raw_result,
                "detections": detections_payload,
                "engine": inference_result.engine,
                "device": inference_result.device,
                "fallbackOccurred": inference_result.fallback_occurred,
                "processed_at": datetime.now(UTC).isoformat(),
            }
            self._repository.mark_done(
                task_id=task_id,
                disease_type=top.label if top else None,
                confidence=top.confidence if top else None,
                bbox=(
                    {
                        "x1": top.bbox.x1,
                        "y1": top.bbox.y1,
                        "x2": top.bbox.x2,
                        "y2": top.bbox.y2,
                    }
                    if top and top.bbox
                    else None
                ),
                raw_result=final_raw,
            )
        except Exception as exc:
            logger.exception("Vision task processing failed", extra={"task_id": task_id})
            self._repository.mark_failed(
                task_id=task_id,
                error_message=str(exc),
                raw_result={**raw_result, "processed_at": datetime.now(UTC).isoformat()},
            )

    def _build_task_response(self, row: dict[str, Any]) -> VisionTaskResponse:
        raw_result = row.get("raw_result") or {}
        detections = raw_result.get("detections") if isinstance(raw_result, dict) else []
        parsed_detections: list[VisionDetectionItem] = []
        if isinstance(detections, list):
            for item in detections:
                if not isinstance(item, dict):
                    continue
                bbox = item.get("bbox")
                parsed_detections.append(
                    VisionDetectionItem(
                        label=str(item.get("label", "unknown")),
                        confidence=float(item.get("confidence", 0)),
                        bbox=(
                            VisionDetectionBox(
                                x1=float(bbox.get("x1", 0)),
                                y1=float(bbox.get("y1", 0)),
                                x2=float(bbox.get("x2", 0)),
                                y2=float(bbox.get("y2", 0)),
                            )
                            if isinstance(bbox, dict)
                            else None
                        ),
                    )
                )

        queued_at = None
        if isinstance(raw_result, dict):
            queued_raw = raw_result.get("queued_at")
            if isinstance(queued_raw, str):
                try:
                    queued_at = datetime.fromisoformat(queued_raw.replace("Z", "+00:00"))
                except ValueError:
                    queued_at = None
        processed_at = self._normalize_utc_datetime(row.get("processed_at"))
        created_at = self._normalize_utc_datetime(row.get("created_at"))
        updated_at = self._normalize_utc_datetime(row.get("updated_at"))
        if created_at is None or updated_at is None:
            raise RuntimeError("Vision task row missing created_at or updated_at timestamp.")

        return VisionTaskResponse(
            taskId=str(row["id"]),
            status=str(row["status"]),
            source=str(row["source"]),
            imageUrl=str(row["image_url"]),
            diseaseType=str(row["disease_type"]) if row.get("disease_type") else None,
            confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
            detections=parsed_detections,
            engine=str(raw_result.get("engine")) if isinstance(raw_result, dict) and raw_result.get("engine") else None,
            device=str(raw_result.get("device")) if isinstance(raw_result, dict) and raw_result.get("device") else None,
            fallbackOccurred=bool(raw_result.get("fallbackOccurred")) if isinstance(raw_result, dict) and "fallbackOccurred" in raw_result else None,
            error=str(raw_result.get("error")) if isinstance(raw_result, dict) and raw_result.get("error") else None,
            queuedAt=queued_at,
            processedAt=processed_at,
            createdAt=created_at,
            updatedAt=updated_at,
        )

    def _is_processing_timeout(self, row: dict[str, Any]) -> bool:
        if str(row.get("status")) != "PROCESSING":
            return False
        created_at = row.get("created_at")
        if not isinstance(created_at, datetime):
            return False
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        timeout_minutes = max(1, self._settings.vision_processing_timeout_minutes)
        return datetime.now(UTC) - created_at > timedelta(minutes=timeout_minutes)

    def _build_timeout_raw_result(self, row: dict[str, Any]) -> dict[str, Any]:
        base = row.get("raw_result")
        payload = base.copy() if isinstance(base, dict) else {}
        payload["timed_out"] = True
        payload["processed_at"] = datetime.now(UTC).isoformat()
        return payload

    @staticmethod
    def _normalize_utc_datetime(value: Any) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    async def _emit_task_event(self, event_type: str, task: VisionTaskResponse) -> None:
        if self._event_hub is None:
            return
        await self._event_hub.publish(
            {
                "type": event_type,
                "task": task.model_dump(mode="json"),
            }
        )
