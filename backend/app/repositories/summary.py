from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings


class CopilotSummaryRepository:
    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def fetch_metric_stats(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        provider: str | None,
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
                value AS latest_value
            FROM samples
            ORDER BY metric, recorded_at DESC, device_id ASC
        )
        SELECT
            summary.metric,
            latest.latest_value,
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
        provider: str | None,
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

    def read_summary_cache(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str | None,
    ) -> dict[str, Any] | None:
        sql = """
        SELECT payload, generated_at
        FROM copilot_summary_cache
        WHERE
            hours = %s
            AND zone = %s
            AND provider = %s
        ORDER BY generated_at DESC
        LIMIT 1
        """
        rows = self._fetch_all(sql, [hours, zone or "", provider or ""])
        if not rows:
            return None
        return rows[0]

    def write_summary_cache(
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
                cursor.execute(sql, [hours, zone or "", provider or "", Jsonb(payload)])
            conn.commit()

    def _build_sample_cte(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        provider: str | None,
    ) -> tuple[str, list[Any]]:
        params: list[Any] = [start_utc, end_utc]
        conditions = [
            "sample.value IS NOT NULL",
            "sensor_data.recorded_at >= %s",
            "sensor_data.recorded_at <= %s",
            "COALESCE(sensor_data.extras->>'source', '') = 'hoogendoorn'",
        ]
        if zone:
            conditions.append("sensor_data.greenhouse_zone = %s")
            params.append(zone)
        if provider:
            conditions.append("COALESCE(sensor_data.extras->>'provider', '') = %s")
            params.append(provider)

        cte_sql = f"""
        WITH samples AS (
            SELECT
                sensor_data.recorded_at,
                sensor_data.greenhouse_zone,
                sensor_data.device_id,
                sample.metric,
                sample.value::double precision AS value
            FROM sensor_data
            CROSS JOIN LATERAL (
                VALUES
                    ('temperature', sensor_data.temperature),
                    ('humidity', sensor_data.humidity),
                    ('ec', sensor_data.ec),
                    ('ph', sensor_data.ph)
            ) AS sample(metric, value)
            WHERE {' AND '.join(conditions)}
        )
        """
        return cte_sql, params

    def _fetch_all(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
