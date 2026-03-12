from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings


class VisionTaskRepository:
    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def create_task(
        self,
        *,
        task_id: str,
        image_url: str,
        source: str,
        uploaded_by_id: str | None,
        captured_at: datetime | None,
        raw_result: dict[str, Any],
    ) -> dict[str, Any]:
        sql = """
        INSERT INTO detections (
            id,
            status,
            source,
            image_url,
            raw_result,
            captured_at,
            uploaded_by_id,
            created_at,
            updated_at
        )
        VALUES (
            %(id)s,
            %(status)s::"DetectionStatus",
            %(source)s::"DetectionSource",
            %(image_url)s,
            %(raw_result)s,
            %(captured_at)s,
            %(uploaded_by_id)s,
            NOW(),
            NOW()
        )
        RETURNING id, status, source, image_url, disease_type, confidence, bbox, raw_result, created_at, updated_at, processed_at
        """
        payload = {
            "id": task_id,
            "status": "PROCESSING",
            "source": source,
            "image_url": image_url,
            "raw_result": Jsonb(raw_result),
            "captured_at": captured_at,
            "uploaded_by_id": uploaded_by_id,
        }
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, payload)
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to create detection task.")
        return row

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        sql = """
        SELECT
            id,
            status,
            source,
            image_url,
            disease_type,
            confidence,
            bbox,
            raw_result,
            created_at,
            updated_at,
            processed_at
        FROM detections
        WHERE id = %s
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, (task_id,))
                return cursor.fetchone()

    def list_recent(self, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            id,
            status,
            source,
            image_url,
            disease_type,
            confidence,
            bbox,
            raw_result,
            created_at,
            updated_at,
            processed_at
        FROM detections
        ORDER BY created_at DESC
        LIMIT %s
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, (limit,))
                return list(cursor.fetchall())

    def mark_done(
        self,
        *,
        task_id: str,
        disease_type: str | None,
        confidence: float | None,
        bbox: dict[str, Any] | None,
        raw_result: dict[str, Any],
    ) -> None:
        sql = """
        UPDATE detections
        SET
            status = 'DONE'::"DetectionStatus",
            disease_type = %(disease_type)s,
            confidence = %(confidence)s,
            bbox = %(bbox)s,
            raw_result = %(raw_result)s,
            processed_at = NOW(),
            updated_at = NOW()
        WHERE id = %(task_id)s
        """
        payload = {
            "task_id": task_id,
            "disease_type": disease_type,
            "confidence": confidence,
            "bbox": Jsonb(bbox) if bbox is not None else None,
            "raw_result": Jsonb(raw_result),
        }
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, payload)
            conn.commit()

    def mark_failed(self, *, task_id: str, error_message: str, raw_result: dict[str, Any]) -> None:
        sql = """
        UPDATE detections
        SET
            status = 'FAILED'::"DetectionStatus",
            raw_result = %(raw_result)s,
            processed_at = NOW(),
            updated_at = NOW()
        WHERE id = %(task_id)s
        """
        payload = {
            "task_id": task_id,
            "raw_result": Jsonb({**raw_result, "error": error_message}),
        }
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, payload)
            conn.commit()

    def mark_processing_timeouts(self, *, timeout_minutes: int, reason: str) -> int:
        sql = """
        UPDATE detections
        SET
            status = 'FAILED'::"DetectionStatus",
            raw_result = COALESCE(raw_result, '{}'::jsonb) || jsonb_build_object(
                'error', %s::text,
                'processed_at', NOW()::text
            ),
            processed_at = NOW(),
            updated_at = NOW()
        WHERE
            status = 'PROCESSING'::"DetectionStatus"
            AND created_at <= NOW() - (%s::int * INTERVAL '1 minute')
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (reason, timeout_minutes))
                affected = cursor.rowcount
            conn.commit()
        return int(affected)
