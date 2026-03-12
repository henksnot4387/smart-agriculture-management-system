from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings


class AIInsightsRepository:
    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def refresh_sensor_24h_samples(self, *, provider: str) -> dict[str, int]:
        upsert_sql = """
        INSERT INTO copilot_rt.sensor_24h_samples (
            recorded_at,
            greenhouse_zone,
            device_id,
            metric,
            value,
            source,
            provider,
            extras,
            collected_at
        )
        SELECT
            sensor_data.recorded_at,
            COALESCE(sensor_data.greenhouse_zone, ''),
            COALESCE(sensor_data.device_id, ''),
            sample.metric,
            sample.value::double precision,
            COALESCE(sensor_data.extras->>'source', ''),
            COALESCE(sensor_data.extras->>'provider', ''),
            sensor_data.extras,
            NOW()
        FROM sensor_data
        CROSS JOIN LATERAL (
            VALUES
                ('temperature', sensor_data.temperature),
                ('humidity', sensor_data.humidity),
                ('ec', sensor_data.ec),
                ('ph', sensor_data.ph)
        ) AS sample(metric, value)
        WHERE
            sample.value IS NOT NULL
            AND sensor_data.recorded_at >= NOW() - INTERVAL '24 hours'
            AND COALESCE(sensor_data.extras->>'source', '') = 'hoogendoorn'
            AND COALESCE(sensor_data.extras->>'provider', '') = %s
        ON CONFLICT (recorded_at, greenhouse_zone, device_id, metric, provider)
        DO UPDATE SET
            value = EXCLUDED.value,
            source = EXCLUDED.source,
            extras = EXCLUDED.extras,
            collected_at = NOW()
        """
        purge_sql = """
        DELETE FROM copilot_rt.sensor_24h_samples
        WHERE provider = %s AND recorded_at < NOW() - INTERVAL '24 hours'
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(upsert_sql, [provider])
                upserted = cursor.rowcount if cursor.rowcount is not None else 0
                cursor.execute(purge_sql, [provider])
                purged = cursor.rowcount if cursor.rowcount is not None else 0
            conn.commit()
        return {
            "upserted": int(upserted),
            "purged": int(purged),
        }

    def get_latest_sample_at(self, *, provider: str, zone: str | None) -> datetime | None:
        params: list[Any] = [provider]
        zone_sql = ""
        if zone:
            zone_sql = "AND greenhouse_zone = %s"
            params.append(zone)
        rows = self._fetch_all(
            f"""
            SELECT MAX(recorded_at) AS latest_sample_at
            FROM copilot_rt.sensor_24h_samples
            WHERE provider = %s {zone_sql}
            """,
            params,
        )
        row = rows[0] if rows else {}
        latest_sample_at = row.get("latest_sample_at")
        return latest_sample_at if isinstance(latest_sample_at, datetime) else None

    def fetch_metric_stats(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        provider: str,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            provider=provider,
        )
        sql = f"""
        {cte_sql},
        summary AS (
            SELECT
                metric,
                AVG(value)::double precision AS avg_value,
                MIN(value)::double precision AS min_value,
                MAX(value)::double precision AS max_value,
                COUNT(*)::int AS sample_count
            FROM samples
            GROUP BY metric
        ),
        latest AS (
            SELECT DISTINCT ON (metric)
                metric,
                value AS latest_value,
                recorded_at AS latest_recorded_at
            FROM samples
            ORDER BY metric, recorded_at DESC, device_id ASC
        )
        SELECT
            summary.metric,
            latest.latest_value,
            latest.latest_recorded_at,
            summary.avg_value,
            summary.min_value,
            summary.max_value,
            summary.sample_count
        FROM summary
        JOIN latest USING (metric)
        ORDER BY summary.metric ASC
        """
        return self._fetch_all(sql, params)

    def fetch_metric_anomalies(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        provider: str,
        temperature_low: float,
        temperature_high: float,
        humidity_low: float,
        humidity_high: float,
        ec_low: float,
        ec_high: float,
        ph_low: float,
        ph_high: float,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            provider=provider,
        )
        sql = f"""
        {cte_sql},
        ordered AS (
            SELECT
                metric,
                recorded_at,
                value,
                LEAD(recorded_at) OVER (PARTITION BY metric ORDER BY recorded_at) AS next_recorded_at
            FROM samples
        ),
        anomaly AS (
            SELECT
                metric,
                CASE
                    WHEN metric = 'temperature' THEN value < %s OR value > %s
                    WHEN metric = 'humidity' THEN value < %s OR value > %s
                    WHEN metric = 'ec' THEN value < %s OR value > %s
                    WHEN metric = 'ph' THEN value < %s OR value > %s
                    ELSE FALSE
                END AS is_anomaly,
                recorded_at,
                COALESCE(next_recorded_at, %s) AS next_recorded_at
            FROM ordered
        )
        SELECT
            metric,
            COUNT(*) FILTER (WHERE is_anomaly)::int AS anomalous_samples,
            COALESCE(
                SUM(
                    CASE
                        WHEN is_anomaly THEN EXTRACT(EPOCH FROM (LEAST(next_recorded_at, %s) - recorded_at))
                        ELSE 0
                    END
                ),
                0
            )::double precision AS anomaly_seconds
        FROM anomaly
        GROUP BY metric
        ORDER BY metric ASC
        """
        params.extend(
            [
                temperature_low,
                temperature_high,
                humidity_low,
                humidity_high,
                ec_low,
                ec_high,
                ph_low,
                ph_high,
                end_utc,
                end_utc,
            ]
        )
        return self._fetch_all(sql, params)

    def fetch_zone_risks(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        provider: str,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=None,
            provider=provider,
        )
        sql = f"""
        {cte_sql},
        ordered AS (
            SELECT
                greenhouse_zone,
                metric,
                recorded_at,
                value,
                LEAD(recorded_at) OVER (PARTITION BY greenhouse_zone, metric ORDER BY recorded_at) AS next_recorded_at
            FROM samples
        ),
        anomaly AS (
            SELECT
                greenhouse_zone,
                metric,
                CASE
                    WHEN metric = 'temperature' THEN value < 10 OR value > 35
                    WHEN metric = 'humidity' THEN value < 40 OR value > 95
                    WHEN metric = 'ec' THEN value < 1 OR value > 5
                    WHEN metric = 'ph' THEN value < 5 OR value > 7.5
                    ELSE FALSE
                END AS is_anomaly,
                recorded_at,
                COALESCE(next_recorded_at, %s) AS next_recorded_at
            FROM ordered
        )
        SELECT
            greenhouse_zone AS zone,
            COUNT(*) FILTER (WHERE is_anomaly)::int AS anomalous_samples,
            COALESCE(
                SUM(
                    CASE
                        WHEN is_anomaly THEN EXTRACT(EPOCH FROM (LEAST(next_recorded_at, %s) - recorded_at))
                        ELSE 0
                    END
                ),
                0
            )::double precision / 60 AS anomaly_minutes
        FROM anomaly
        GROUP BY greenhouse_zone
        ORDER BY anomaly_minutes DESC, anomalous_samples DESC, greenhouse_zone ASC
        LIMIT 20
        """
        params.extend([end_utc, end_utc])
        return self._fetch_all(sql, params)

    def fetch_metric_trends(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        provider: str,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            provider=provider,
        )
        sql = f"""
        {cte_sql}
        SELECT
            metric,
            date_trunc('hour', recorded_at) AS bucket_start,
            AVG(value)::double precision AS avg_value,
            MIN(value)::double precision AS min_value,
            MAX(value)::double precision AS max_value,
            COUNT(*)::int AS sample_count
        FROM samples
        GROUP BY metric, date_trunc('hour', recorded_at)
        ORDER BY metric ASC, bucket_start ASC
        """
        return self._fetch_all(sql, params)

    def fetch_disease_counts(self, *, start_utc: datetime, end_utc: datetime) -> list[dict[str, Any]]:
        sql = """
        SELECT
            COALESCE(NULLIF(disease_type, ''), 'UNKNOWN') AS disease_type,
            COUNT(*)::int AS total_count
        FROM detections
        WHERE
            status = 'DONE'::"DetectionStatus"
            AND created_at >= %s
            AND created_at <= %s
        GROUP BY COALESCE(NULLIF(disease_type, ''), 'UNKNOWN')
        ORDER BY total_count DESC, disease_type ASC
        LIMIT 10
        """
        return self._fetch_all(sql, [start_utc, end_utc])

    def create_summary_run(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str,
        mode: str,
        engine_provider: str,
        engine_model: str | None,
        fallback_used: bool,
        freshness_status: str,
        latest_sample_at: datetime | None,
        payload: dict[str, Any],
    ) -> int:
        sql = """
        INSERT INTO copilot_rt.summary_runs (
            hours,
            zone,
            provider,
            mode,
            engine_provider,
            engine_model,
            fallback_used,
            freshness_status,
            latest_sample_at,
            payload,
            generated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    [
                        hours,
                        zone or "",
                        provider,
                        mode,
                        engine_provider,
                        engine_model,
                        fallback_used,
                        freshness_status,
                        latest_sample_at,
                        Jsonb(payload),
                    ],
                )
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to insert summary run.")
        return int(row[0])

    def read_latest_summary_run(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str,
    ) -> dict[str, Any] | None:
        rows = self._fetch_all(
            """
            SELECT id, payload, generated_at
            FROM copilot_rt.summary_runs
            WHERE hours = %s AND zone = %s AND provider = %s
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            [hours, zone or "", provider],
        )
        return rows[0] if rows else None

    def create_recommendation_drafts(
        self,
        *,
        summary_run_id: int | None,
        hours: int,
        zone: str | None,
        provider: str,
        llm_provider: str,
        llm_model: str | None,
        fallback_used: bool,
        drafts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sql = """
        INSERT INTO copilot_rt.recommendation_drafts (
            id,
            summary_run_id,
            status,
            title,
            description,
            reason,
            priority,
            suggested_role,
            due_hours,
            llm_provider,
            llm_model,
            fallback_used,
            knowledge_refs,
            data_evidence,
            knowledge_evidence,
            hours,
            zone,
            provider,
            metadata,
            created_at,
            updated_at
        )
        VALUES (
            %s::uuid,
            %s,
            'PENDING',
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s::jsonb,
            %s::jsonb,
            %s::jsonb,
            %s,
            %s,
            %s,
            %s::jsonb,
            NOW(),
            NOW()
        )
        RETURNING
            id::text AS draft_id,
            title,
            description,
            reason,
            priority,
            suggested_role,
            due_hours,
            status,
            llm_provider,
            llm_model,
            fallback_used,
            knowledge_refs,
            data_evidence,
            knowledge_evidence,
            created_at,
            confirmed_at,
            task_id::text AS task_id
        """
        rows: list[dict[str, Any]] = []
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                for draft in drafts:
                    cursor.execute(
                        sql,
                        [
                            str(uuid4()),
                            summary_run_id,
                            draft["title"],
                            draft["description"],
                            draft["reason"],
                            draft["priority"],
                            draft["suggested_role"],
                            draft["due_hours"],
                            llm_provider,
                            llm_model,
                            fallback_used,
                            Jsonb(draft.get("knowledge_refs") or []),
                            Jsonb(draft.get("data_evidence") or []),
                            Jsonb(draft.get("knowledge_evidence") or []),
                            hours,
                            zone or "",
                            provider,
                            Jsonb(draft.get("metadata") or {}),
                        ],
                    )
                    row = cursor.fetchone()
                    if row:
                        rows.append(dict(row))
            conn.commit()
        return rows

    def list_recommendation_drafts(
        self,
        *,
        limit: int,
        status: str | None,
    ) -> tuple[int, list[dict[str, Any]]]:
        params: list[Any] = []
        where_clauses: list[str] = []
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_rows = self._fetch_all(
            f"""
            SELECT COUNT(*)::int AS total
            FROM copilot_rt.recommendation_drafts
            {where_sql}
            """,
            params,
        )
        total = int((count_rows[0] if count_rows else {}).get("total") or 0)
        rows = self._fetch_all(
            f"""
            SELECT
                id::text AS draft_id,
                title,
                description,
                reason,
                priority,
                suggested_role,
                due_hours,
                status,
                llm_provider,
                llm_model,
                fallback_used,
                knowledge_refs,
                data_evidence,
                knowledge_evidence,
                created_at,
                confirmed_at,
                task_id::text AS task_id
            FROM copilot_rt.recommendation_drafts
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            [*params, limit],
        )
        return total, rows

    def list_pending_recommendation_drafts(self, *, limit: int) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT
                id::text AS draft_id,
                title,
                description,
                reason,
                priority,
                suggested_role,
                due_hours,
                status,
                llm_provider,
                llm_model,
                fallback_used,
                knowledge_refs,
                data_evidence,
                knowledge_evidence,
                created_at,
                confirmed_at,
                task_id::text AS task_id
            FROM copilot_rt.recommendation_drafts
            WHERE status = 'PENDING'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            [limit],
        )
        return rows

    def confirm_recommendation_drafts(
        self,
        *,
        draft_ids: list[str],
        confirmed_by_id: str,
    ) -> list[dict[str, Any]]:
        if not draft_ids:
            return []
        dedup_ids = list(dict.fromkeys(draft_ids))
        selected_sql = """
        SELECT
            id::text AS draft_id,
            title,
            description,
            reason,
            priority,
            suggested_role,
            due_hours,
            llm_provider,
            llm_model,
            fallback_used,
            knowledge_refs,
            data_evidence,
            knowledge_evidence,
            metadata
        FROM copilot_rt.recommendation_drafts
        WHERE id = ANY(%s::uuid[]) AND status = 'PENDING'
        ORDER BY created_at ASC
        FOR UPDATE
        """
        insert_task_sql = """
        INSERT INTO tasks (
            id,
            title,
            description,
            status,
            priority,
            source,
            metadata,
            created_by_id,
            due_at,
            created_at,
            updated_at
        )
        VALUES (
            %s::uuid,
            %s,
            %s,
            'PENDING'::"TaskStatus",
            %s::"TaskPriority",
            'AI'::"TaskSource",
            %s::jsonb,
            %s::uuid,
            %s,
            NOW(),
            NOW()
        )
        RETURNING id::text AS task_id, title, status::text AS status, priority::text AS priority, created_at
        """
        update_draft_sql = """
        UPDATE copilot_rt.recommendation_drafts
        SET
            status = 'CONFIRMED',
            confirmed_by_id = %s::uuid,
            confirmed_at = NOW(),
            task_id = %s::uuid,
            updated_at = NOW()
        WHERE id = %s::uuid
        """

        created_tasks: list[dict[str, Any]] = []
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(selected_sql, [dedup_ids])
                drafts = list(cursor.fetchall())
                if len(drafts) != len(dedup_ids):
                    found_ids = {str(row["draft_id"]) for row in drafts}
                    missing = [item for item in dedup_ids if item not in found_ids]
                    raise ValueError(f"Draft not found or already confirmed: {', '.join(missing)}")

                for draft in drafts:
                    data_evidence = draft.get("data_evidence") or []
                    knowledge_evidence = draft.get("knowledge_evidence") or []
                    if not isinstance(data_evidence, list) or not data_evidence:
                        raise ValueError(
                            f"Draft {draft['draft_id']} missing data evidence; confirmation is blocked."
                        )
                    if not isinstance(knowledge_evidence, list) or not knowledge_evidence:
                        raise ValueError(
                            f"Draft {draft['draft_id']} missing knowledge evidence; confirmation is blocked."
                        )

                now_utc = datetime.now(UTC)
                for draft in drafts:
                    due_hours = int(draft.get("due_hours") or 24)
                    task_id = str(uuid4())
                    task_metadata = {
                        "aiInsights": {
                            "draftId": draft["draft_id"],
                            "reason": draft.get("reason"),
                            "suggestedRole": draft.get("suggested_role"),
                            "dueHours": due_hours,
                            "llm": {
                                "provider": draft.get("llm_provider"),
                                "model": draft.get("llm_model"),
                                "fallbackUsed": bool(draft.get("fallback_used")),
                            },
                            "knowledgeRefs": draft.get("knowledge_refs") or [],
                            "dataEvidence": draft.get("data_evidence") or [],
                            "knowledgeEvidence": draft.get("knowledge_evidence") or [],
                        }
                    }
                    due_at = now_utc + timedelta(hours=max(1, min(due_hours, 168)))
                    cursor.execute(
                        insert_task_sql,
                        [
                            task_id,
                            draft["title"],
                            draft["description"],
                            draft["priority"],
                            Jsonb(task_metadata),
                            confirmed_by_id,
                            due_at,
                        ],
                    )
                    task_row = cursor.fetchone()
                    cursor.execute(update_draft_sql, [confirmed_by_id, task_id, draft["draft_id"]])
                    if task_row:
                        created_tasks.append(
                            {
                                "draft_id": draft["draft_id"],
                                "task_id": task_row["task_id"],
                                "title": task_row["title"],
                                "status": task_row["status"],
                                "priority": task_row["priority"],
                                "created_at": task_row["created_at"],
                            }
                        )
            conn.commit()

        return created_tasks

    def _build_sample_cte(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        provider: str,
    ) -> tuple[str, list[Any]]:
        params: list[Any] = [start_utc, end_utc, provider]
        conditions = [
            "value IS NOT NULL",
            "recorded_at >= %s",
            "recorded_at <= %s",
            "provider = %s",
        ]
        if zone:
            conditions.append("greenhouse_zone = %s")
            params.append(zone)

        cte_sql = f"""
        WITH samples AS (
            SELECT
                recorded_at,
                greenhouse_zone,
                device_id,
                metric,
                value
            FROM copilot_rt.sensor_24h_samples
            WHERE {' AND '.join(conditions)}
        )
        """
        return cte_sql, params

    def _fetch_all(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
