from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import psycopg

from app.core.config import Settings


class ObservabilityRepository:
    _schema_lock_key = 98421077

    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def ensure_schema(self) -> None:
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS observability_http_events (
                id BIGSERIAL PRIMARY KEY,
                request_id TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                route TEXT NOT NULL,
                domain TEXT NOT NULL,
                status_code INT NOT NULL,
                latency_ms DOUBLE PRECISION NOT NULL,
                is_slow BOOLEAN NOT NULL DEFAULT FALSE,
                error_code TEXT,
                user_id TEXT,
                user_role TEXT,
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS observability_http_events_occurred_idx
            ON observability_http_events (occurred_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS observability_http_events_route_idx
            ON observability_http_events (route, occurred_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS observability_http_events_domain_idx
            ON observability_http_events (domain, occurred_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS observability_http_events_status_idx
            ON observability_http_events (status_code, occurred_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS observability_http_events_slow_idx
            ON observability_http_events (is_slow, occurred_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS observability_http_events_request_idx
            ON observability_http_events (request_id)
            """,
        ]
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [self._schema_lock_key])
                try:
                    for sql in sql_statements:
                        cursor.execute(sql)
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [self._schema_lock_key])
            conn.commit()

    def insert_http_event(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        route: str,
        domain: str,
        status_code: int,
        latency_ms: float,
        is_slow: bool,
        error_code: str | None,
        user_id: str | None,
        user_role: str | None,
    ) -> None:
        sql = """
        INSERT INTO observability_http_events (
            request_id,
            method,
            path,
            route,
            domain,
            status_code,
            latency_ms,
            is_slow,
            error_code,
            user_id,
            user_role
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            request_id,
            method,
            path,
            route,
            domain,
            status_code,
            latency_ms,
            is_slow,
            error_code,
            user_id,
            user_role,
        )
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
            conn.commit()

    def get_overview_metrics(self, *, window_hours: int, slow_threshold_ms: int) -> dict[str, Any]:
        sql = """
        SELECT
            COUNT(*)::BIGINT AS total_requests,
            COUNT(*) FILTER (WHERE status_code >= 400)::BIGINT AS error_requests,
            COUNT(*) FILTER (WHERE latency_ms >= %s)::BIGINT AS slow_requests,
            COALESCE(
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms),
                0
            )::DOUBLE PRECISION AS p95_latency_ms
        FROM observability_http_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
        """
        rows = self._fetch_all(sql, [slow_threshold_ms, window_hours])
        return rows[0] if rows else {
            "total_requests": 0,
            "error_requests": 0,
            "slow_requests": 0,
            "p95_latency_ms": 0.0,
        }

    def list_route_metrics(
        self,
        *,
        window_hours: int,
        slow_threshold_ms: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
            route,
            COUNT(*)::BIGINT AS request_count,
            COUNT(*) FILTER (WHERE status_code >= 400)::BIGINT AS error_count,
            COUNT(*) FILTER (WHERE latency_ms >= %s)::BIGINT AS slow_count,
            COALESCE(AVG(latency_ms), 0)::DOUBLE PRECISION AS avg_latency_ms,
            COALESCE(
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms),
                0
            )::DOUBLE PRECISION AS p95_latency_ms,
            COALESCE(MAX(latency_ms), 0)::DOUBLE PRECISION AS max_latency_ms
        FROM observability_http_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
        GROUP BY route
        ORDER BY error_count DESC, slow_count DESC, request_count DESC, route ASC
        LIMIT %s
        """
        return self._fetch_all(sql, [slow_threshold_ms, window_hours, limit])

    def list_domain_metrics(
        self,
        *,
        window_hours: int,
        slow_threshold_ms: int,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
            domain,
            COUNT(*)::BIGINT AS request_count,
            COUNT(*) FILTER (WHERE status_code >= 400)::BIGINT AS error_count,
            COUNT(*) FILTER (WHERE latency_ms >= %s)::BIGINT AS slow_count
        FROM observability_http_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
        GROUP BY domain
        ORDER BY request_count DESC, domain ASC
        """
        return self._fetch_all(sql, [slow_threshold_ms, window_hours])

    def list_error_code_metrics(self, *, window_hours: int, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            COALESCE(NULLIF(error_code, ''), 'UNKNOWN') AS error_code,
            COUNT(*)::BIGINT AS count
        FROM observability_http_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
          AND status_code >= 400
        GROUP BY COALESCE(NULLIF(error_code, ''), 'UNKNOWN')
        ORDER BY count DESC, error_code ASC
        LIMIT %s
        """
        return self._fetch_all(sql, [window_hours, limit])

    def list_recent_errors(self, *, window_hours: int, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            request_id,
            method,
            path,
            route,
            status_code,
            latency_ms,
            error_code,
            user_id,
            user_role,
            occurred_at
        FROM observability_http_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
          AND status_code >= 400
        ORDER BY occurred_at DESC
        LIMIT %s
        """
        return self._fetch_all(sql, [window_hours, limit])

    def list_recent_slow_requests(
        self,
        *,
        window_hours: int,
        slow_threshold_ms: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
            request_id,
            method,
            path,
            route,
            status_code,
            latency_ms,
            error_code,
            user_id,
            user_role,
            occurred_at
        FROM observability_http_events
        WHERE occurred_at >= NOW() - (%s * INTERVAL '1 hour')
          AND latency_ms >= %s
        ORDER BY latency_ms DESC, occurred_at DESC
        LIMIT %s
        """
        return self._fetch_all(sql, [window_hours, slow_threshold_ms, limit])

    def list_task_failures(self, *, window_hours: int, limit: int) -> list[dict[str, Any]]:
        sql = """
        SELECT
            job_id,
            COUNT(*)::BIGINT AS failed_count,
            MAX(started_at) AS last_failed_at,
            (ARRAY_AGG(error ORDER BY started_at DESC))[1] AS last_error
        FROM scheduler_job_runs
        WHERE status = 'FAILED'
          AND started_at >= NOW() - (%s * INTERVAL '1 hour')
        GROUP BY job_id
        ORDER BY failed_count DESC, last_failed_at DESC, job_id ASC
        LIMIT %s
        """
        return self._fetch_all(sql, [window_hours, limit])

    def _fetch_all(self, sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [dict(row) for row in rows]
