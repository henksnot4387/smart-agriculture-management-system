from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings
from app.scheduler.registry import SchedulerJobDefinition


class SchedulerRepository:
    _schema_lock_key = 98421031

    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def ensure_schema(self) -> None:
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS scheduler_jobs (
                job_id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                interval_seconds INT,
                cron_minute TEXT,
                cron_hour TEXT,
                is_paused BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_run_started_at TIMESTAMPTZ,
                last_run_finished_at TIMESTAMPTZ,
                last_status TEXT,
                last_message TEXT,
                last_error TEXT,
                last_duration_ms INT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS scheduler_job_runs (
                id BIGSERIAL PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES scheduler_jobs(job_id) ON DELETE CASCADE,
                trigger TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                error TEXT,
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                duration_ms INT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS scheduler_job_runs_job_started_idx
            ON scheduler_job_runs (job_id, started_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS scheduler_job_runs_started_idx
            ON scheduler_job_runs (started_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS copilot_summary_cache (
                id BIGSERIAL PRIMARY KEY,
                hours INT NOT NULL,
                zone TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                payload JSONB NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            UPDATE copilot_summary_cache SET zone = '' WHERE zone IS NULL
            """,
            """
            UPDATE copilot_summary_cache SET provider = '' WHERE provider IS NULL
            """,
            """
            ALTER TABLE copilot_summary_cache ALTER COLUMN zone SET DEFAULT ''
            """,
            """
            ALTER TABLE copilot_summary_cache ALTER COLUMN provider SET DEFAULT ''
            """,
            """
            ALTER TABLE copilot_summary_cache ALTER COLUMN zone SET NOT NULL
            """,
            """
            ALTER TABLE copilot_summary_cache ALTER COLUMN provider SET NOT NULL
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS copilot_summary_cache_unique_idx
            ON copilot_summary_cache (hours, zone, provider)
            """,
            """
            CREATE SCHEMA IF NOT EXISTS copilot_rt
            """,
            """
            CREATE TABLE IF NOT EXISTS copilot_rt.sensor_24h_samples (
                recorded_at TIMESTAMPTZ NOT NULL,
                greenhouse_zone TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                metric TEXT NOT NULL,
                value DOUBLE PRECISION NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                extras JSONB,
                collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (recorded_at, greenhouse_zone, device_id, metric, provider)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS copilot_rt_sensor_24h_samples_provider_time_idx
            ON copilot_rt.sensor_24h_samples (provider, recorded_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS copilot_rt_sensor_24h_samples_zone_time_idx
            ON copilot_rt.sensor_24h_samples (greenhouse_zone, recorded_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS copilot_rt.summary_runs (
                id BIGSERIAL PRIMARY KEY,
                hours INT NOT NULL,
                zone TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL,
                engine_provider TEXT NOT NULL,
                engine_model TEXT,
                fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
                freshness_status TEXT NOT NULL,
                latest_sample_at TIMESTAMPTZ,
                payload JSONB NOT NULL,
                generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS copilot_rt_summary_runs_scope_idx
            ON copilot_rt.summary_runs (hours, zone, provider, generated_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS copilot_rt.recommendation_drafts (
                id UUID PRIMARY KEY,
                summary_run_id BIGINT REFERENCES copilot_rt.summary_runs(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                reason TEXT NOT NULL,
                priority TEXT NOT NULL,
                suggested_role TEXT NOT NULL,
                due_hours INT NOT NULL,
                llm_provider TEXT NOT NULL,
                llm_model TEXT,
                fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
                knowledge_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
                data_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                knowledge_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                hours INT NOT NULL DEFAULT 24,
                zone TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                confirmed_by_id UUID,
                confirmed_at TIMESTAMPTZ,
                task_id UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS copilot_rt_recommendation_drafts_status_idx
            ON copilot_rt.recommendation_drafts (status, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS copilot_rt_recommendation_drafts_scope_idx
            ON copilot_rt.recommendation_drafts (provider, zone, created_at DESC)
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS copilot_rt_recommendation_drafts_task_id_idx
            ON copilot_rt.recommendation_drafts (task_id)
            WHERE task_id IS NOT NULL
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

    def upsert_job_definitions(self, jobs: list[SchedulerJobDefinition]) -> None:
        sql = """
        INSERT INTO scheduler_jobs (
            job_id,
            task_name,
            name,
            description,
            schedule_type,
            schedule_value,
            interval_seconds,
            cron_minute,
            cron_hour,
            created_at,
            updated_at
        )
        VALUES (
            %(job_id)s,
            %(task_name)s,
            %(name)s,
            %(description)s,
            %(schedule_type)s,
            %(schedule_value)s,
            %(interval_seconds)s,
            %(cron_minute)s,
            %(cron_hour)s,
            NOW(),
            NOW()
        )
        ON CONFLICT (job_id)
        DO UPDATE SET
            task_name = EXCLUDED.task_name,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            schedule_type = EXCLUDED.schedule_type,
            schedule_value = EXCLUDED.schedule_value,
            interval_seconds = EXCLUDED.interval_seconds,
            cron_minute = EXCLUDED.cron_minute,
            cron_hour = EXCLUDED.cron_hour,
            updated_at = NOW()
        """

        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                for job in jobs:
                    cursor.execute(
                        sql,
                        {
                            "job_id": job.job_id,
                            "task_name": job.task_name,
                            "name": job.name,
                            "description": job.description,
                            "schedule_type": job.schedule_type,
                            "schedule_value": job.schedule_value,
                            "interval_seconds": job.interval_seconds,
                            "cron_minute": job.cron_minute,
                            "cron_hour": job.cron_hour,
                        },
                    )
            conn.commit()

    def list_jobs(self) -> list[dict[str, Any]]:
        sql = """
        SELECT
            job_id,
            task_name,
            name,
            description,
            schedule_type,
            schedule_value,
            interval_seconds,
            cron_minute,
            cron_hour,
            is_paused,
            last_run_started_at,
            last_run_finished_at,
            last_status,
            last_message,
            last_error,
            last_duration_ms,
            updated_at
        FROM scheduler_jobs
        ORDER BY name ASC
        """
        return self._fetch_all(sql, [])

    def list_runs(self, *, limit: int, job_id: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if job_id:
            where = "WHERE job_id = %s"
            params.append(job_id)

        params.append(limit)
        sql = f"""
        SELECT
            id,
            job_id,
            trigger,
            status,
            message,
            error,
            started_at,
            finished_at,
            duration_ms
        FROM scheduler_job_runs
        {where}
        ORDER BY started_at DESC
        LIMIT %s
        """
        return self._fetch_all(sql, params)

    def create_run(self, *, job_id: str, trigger: str) -> int:
        sql = """
        INSERT INTO scheduler_job_runs (job_id, trigger, status, started_at)
        VALUES (%s, %s, 'RUNNING', NOW())
        RETURNING id
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (job_id, trigger))
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to create scheduler run.")
        return int(row[0])

    def finish_run(
        self,
        *,
        run_id: int,
        status: str,
        message: str | None,
        error: str | None,
        duration_ms: int,
    ) -> None:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE scheduler_job_runs
                    SET
                        status = %s,
                        message = %s,
                        error = %s,
                        finished_at = NOW(),
                        duration_ms = %s
                    WHERE id = %s
                    """,
                    (status, message, error, duration_ms, run_id),
                )
                cursor.execute(
                    """
                    UPDATE scheduler_jobs
                    SET
                        last_run_started_at = run.started_at,
                        last_run_finished_at = run.finished_at,
                        last_status = run.status,
                        last_message = run.message,
                        last_error = run.error,
                        last_duration_ms = run.duration_ms,
                        updated_at = NOW()
                    FROM (
                        SELECT id, job_id, started_at, finished_at, status, message, error, duration_ms
                        FROM scheduler_job_runs
                        WHERE id = %s
                    ) AS run
                    WHERE scheduler_jobs.job_id = run.job_id
                    """,
                    (run_id,),
                )
            conn.commit()

    def set_paused(self, *, job_id: str, paused: bool) -> bool:
        sql = """
        UPDATE scheduler_jobs
        SET is_paused = %s, updated_at = NOW()
        WHERE job_id = %s
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (paused, job_id))
                changed = cursor.rowcount > 0
            conn.commit()
        return changed

    def get_job(self, *, job_id: str) -> dict[str, Any] | None:
        rows = self._fetch_all(
            """
            SELECT
                job_id,
                task_name,
                name,
                description,
                schedule_type,
                schedule_value,
                interval_seconds,
                cron_minute,
                cron_hour,
                is_paused,
                last_run_started_at,
                last_run_finished_at,
                last_status,
                last_message,
                last_error,
                last_duration_ms,
                updated_at
            FROM scheduler_jobs
            WHERE job_id = %s
            LIMIT 1
            """,
            [job_id],
        )
        return rows[0] if rows else None

    def is_job_paused(self, *, job_id: str) -> bool:
        row = self.get_job(job_id=job_id)
        return bool(row and row.get("is_paused"))

    def upsert_summary_cache(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str | None,
        payload: dict[str, Any],
    ) -> None:
        sql = """
        INSERT INTO copilot_summary_cache (hours, zone, provider, payload, generated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (hours, zone, provider)
        DO UPDATE SET
            payload = EXCLUDED.payload,
            generated_at = NOW()
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (hours, zone or "", provider or "", Jsonb(payload)))
            conn.commit()

    def get_health(self) -> dict[str, Any]:
        rows = self._fetch_all(
            """
            SELECT
                COUNT(*)::int AS total_jobs,
                COUNT(*) FILTER (WHERE is_paused)::int AS paused_jobs,
                MAX(last_run_finished_at) AS latest_finished_at
            FROM scheduler_jobs
            """,
            [],
        )
        row = rows[0] if rows else {}
        return {
            "total_jobs": int(row.get("total_jobs") or 0),
            "paused_jobs": int(row.get("paused_jobs") or 0),
            "latest_finished_at": row.get("latest_finished_at"),
            "timestamp": datetime.now(UTC),
        }

    def _fetch_all(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
