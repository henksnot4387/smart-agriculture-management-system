from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg

from app.core.config import Settings


class OpsRepository:
    _schema_lock_key = 98421092

    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def fetch_catalog_coverage(self, *, provider: str, lookback_hours: int) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
        SELECT
            COALESCE(extras->>'control_type_id', '') AS control_type_id,
            COALESCE(extras->>'parameter_id', '') AS parameter_id,
            MAX(recorded_at) AS latest_sample_at
        FROM ops_metric_samples
        WHERE
            provider = %s
            AND recorded_at >= NOW() - make_interval(hours => %s)
        GROUP BY COALESCE(extras->>'control_type_id', ''), COALESCE(extras->>'parameter_id', '')
        """
        return self._fetch_all(sql, [provider, lookback_hours])

    def fetch_latest_zone_metrics(self, *, provider: str, lookback_hours: int) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
        WITH ranked AS (
            SELECT
                greenhouse_zone,
                metric_key,
                display_name,
                module,
                module_label,
                area,
                value_type,
                unit,
                value,
                recorded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY greenhouse_zone, metric_key
                    ORDER BY recorded_at DESC, collected_at DESC
                ) AS rn
            FROM ops_metric_samples
            WHERE
                provider = %s
                AND recorded_at >= NOW() - make_interval(hours => %s)
        )
        SELECT
            greenhouse_zone,
            metric_key,
            display_name,
            module,
            module_label,
            area,
            value_type,
            unit,
            value,
            recorded_at
        FROM ranked
        WHERE rn = 1
        ORDER BY greenhouse_zone ASC, module ASC, metric_key ASC
        """
        return self._fetch_all(sql, [provider, lookback_hours])

    def fetch_latest_sample_at(self, *, provider: str) -> datetime | None:
        self.ensure_schema()
        sql = """
        SELECT MAX(recorded_at) AS latest_sample_at
        FROM ops_metric_samples
        WHERE provider = %s
        """
        rows = self._fetch_all(sql, [provider])
        row = rows[0] if rows else {}
        latest_sample_at = row.get("latest_sample_at")
        return latest_sample_at if isinstance(latest_sample_at, datetime) else None

    def fetch_trend_points(
        self,
        *,
        provider: str,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
    ) -> list[dict[str, Any]]:
        self.ensure_schema()
        params: list[Any] = [provider, start_utc, end_utc]
        zone_sql = ""
        if zone:
            zone_sql = "AND greenhouse_zone = %s"
            params.append(zone)
        sql = f"""
        SELECT
            metric_key,
            MAX(display_name) AS display_name,
            MAX(module) AS module,
            MAX(module_label) AS module_label,
            date_trunc('hour', recorded_at) AS bucket_start,
            AVG(value)::double precision AS avg_value,
            MIN(value)::double precision AS min_value,
            MAX(value)::double precision AS max_value,
            COUNT(*)::int AS sample_count
        FROM ops_metric_samples
        WHERE
            provider = %s
            AND recorded_at >= %s
            AND recorded_at <= %s
            {zone_sql}
        GROUP BY metric_key, date_trunc('hour', recorded_at)
        ORDER BY bucket_start ASC, metric_key ASC
        """
        return self._fetch_all(sql, params)

    def ensure_schema(self) -> None:
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
                cursor.execute("SELECT pg_advisory_lock(%s)", [self._schema_lock_key])
                try:
                    for statement in sql_statements:
                        cursor.execute(statement)
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [self._schema_lock_key])
            conn.commit()

    def _fetch_all(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
