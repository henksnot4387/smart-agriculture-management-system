from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings

logger = logging.getLogger("app.integrations.hoogendoorn.repository")


class SensorDataRepository:
    _ops_schema_lock_key = 98421092

    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def latest_recorded_at(self, provider_name: str) -> datetime | None:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT MAX(recorded_at)
                    FROM sensor_data
                    WHERE COALESCE(extras->>'source', '') = 'hoogendoorn'
                      AND COALESCE(extras->>'provider', '') = %s
                    """,
                    (provider_name,),
                )
                row = cursor.fetchone()
                return row[0] if row else None

    def upsert_sensor_rows(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        sql = """
        INSERT INTO sensor_data (
            recorded_at,
            id,
            greenhouse_zone,
            device_id,
            temperature,
            humidity,
            ec,
            ph,
            extras
        )
        VALUES (
            %(recorded_at)s,
            %(id)s,
            %(greenhouse_zone)s,
            %(device_id)s,
            %(temperature)s,
            %(humidity)s,
            %(ec)s,
            %(ph)s,
            %(extras)s
        )
        ON CONFLICT (recorded_at, id) DO UPDATE SET
            greenhouse_zone = EXCLUDED.greenhouse_zone,
            device_id = EXCLUDED.device_id,
            temperature = COALESCE(EXCLUDED.temperature, sensor_data.temperature),
            humidity = COALESCE(EXCLUDED.humidity, sensor_data.humidity),
            ec = COALESCE(EXCLUDED.ec, sensor_data.ec),
            ph = COALESCE(EXCLUDED.ph, sensor_data.ph),
            extras = COALESCE(sensor_data.extras, '{}'::jsonb) || COALESCE(EXCLUDED.extras, '{}'::jsonb)
        """

        payload = [{**row, "extras": Jsonb(row["extras"])} for row in rows]
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.executemany(sql, payload)
            conn.commit()

        logger.info("Upserted sensor rows", extra={"row_count": len(rows)})
        return len(rows)

    def upsert_metric_rows(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        self._ensure_ops_metric_table()

        sql = """
        INSERT INTO ops_metric_samples (
            recorded_at,
            sample_id,
            greenhouse_zone,
            device_id,
            metric_key,
            display_name,
            module,
            module_label,
            area,
            value_type,
            unit,
            value,
            source,
            provider,
            extras,
            collected_at
        )
        VALUES (
            %(recorded_at)s,
            %(sample_id)s::uuid,
            %(greenhouse_zone)s,
            %(device_id)s,
            %(metric_key)s,
            %(display_name)s,
            %(module)s,
            %(module_label)s,
            %(area)s,
            %(value_type)s,
            %(unit)s,
            %(value)s,
            %(source)s,
            %(provider)s,
            %(extras)s,
            NOW()
        )
        ON CONFLICT (recorded_at, provider, device_id, metric_key) DO UPDATE SET
            greenhouse_zone = EXCLUDED.greenhouse_zone,
            display_name = EXCLUDED.display_name,
            module = EXCLUDED.module,
            module_label = EXCLUDED.module_label,
            area = EXCLUDED.area,
            value_type = EXCLUDED.value_type,
            unit = EXCLUDED.unit,
            value = EXCLUDED.value,
            source = EXCLUDED.source,
            extras = COALESCE(ops_metric_samples.extras, '{}'::jsonb) || COALESCE(EXCLUDED.extras, '{}'::jsonb),
            collected_at = NOW()
        """
        payload = [{**row, "extras": Jsonb(row["extras"])} for row in rows]
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.executemany(sql, payload)
            conn.commit()
        logger.info("Upserted ops metric rows", extra={"row_count": len(rows)})
        return len(rows)

    def _ensure_ops_metric_table(self) -> None:
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS ops_metric_samples (
                recorded_at TIMESTAMPTZ NOT NULL,
                sample_id UUID NOT NULL,
                greenhouse_zone TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                metric_key TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                module TEXT NOT NULL DEFAULT 'other',
                module_label TEXT NOT NULL DEFAULT '其他',
                area TEXT NOT NULL DEFAULT 'utility',
                value_type TEXT NOT NULL DEFAULT 'numeric',
                unit TEXT NOT NULL DEFAULT 'raw',
                value DOUBLE PRECISION NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                extras JSONB,
                collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (recorded_at, provider, device_id, metric_key)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS ops_metric_samples_provider_time_idx
            ON ops_metric_samples (provider, recorded_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS ops_metric_samples_zone_time_idx
            ON ops_metric_samples (greenhouse_zone, recorded_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS ops_metric_samples_metric_time_idx
            ON ops_metric_samples (metric_key, recorded_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS ops_metric_samples_module_time_idx
            ON ops_metric_samples (module, recorded_at DESC)
            """,
        ]

        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [self._ops_schema_lock_key])
                try:
                    for sql in sql_statements:
                        cursor.execute(sql)
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [self._ops_schema_lock_key])
            conn.commit()
