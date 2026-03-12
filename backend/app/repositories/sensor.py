from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg

from app.core.config import Settings
from app.schemas.sensor import SensorMetric

VALID_METRIC_NAMES = tuple(metric.value for metric in SensorMetric)
SERIES_SOURCE_RAW = "raw"
SERIES_SOURCE_15M = "15m"
SERIES_SOURCE_1D = "1d"


class SensorQueryRepository:
    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def fetch_raw_samples(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        metrics: list[SensorMetric],
        limit: int,
        provider: str | None,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
            provider=provider,
        )
        sql = f"""
        {cte_sql}
        SELECT
            recorded_at,
            greenhouse_zone,
            device_id,
            metric,
            value,
            provider,
            source,
            extras
        FROM samples
        ORDER BY recorded_at DESC, greenhouse_zone ASC, device_id ASC, metric ASC
        LIMIT %s
        """
        params.append(limit)
        return self._fetch_all(sql, params)

    def fetch_series_points(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        metrics: list[SensorMetric],
        bucket_interval: str,
        provider: str | None,
        series_source: str = SERIES_SOURCE_RAW,
    ) -> list[dict[str, Any]]:
        if series_source == SERIES_SOURCE_RAW:
            return self._fetch_series_from_raw(
                start_utc=start_utc,
                end_utc=end_utc,
                zone=zone,
                metrics=metrics,
                bucket_interval=bucket_interval,
                provider=provider,
            )
        if series_source == SERIES_SOURCE_15M:
            return self._fetch_series_from_cagg(
                view_name="sensor_samples_15m",
                start_utc=start_utc,
                end_utc=end_utc,
                zone=zone,
                metrics=metrics,
                bucket_interval=bucket_interval,
                provider=provider,
            )
        if series_source == SERIES_SOURCE_1D:
            return self._fetch_series_from_cagg(
                view_name="sensor_samples_1d",
                start_utc=start_utc,
                end_utc=end_utc,
                zone=zone,
                metrics=metrics,
                bucket_interval=bucket_interval,
                provider=provider,
            )
        raise ValueError(f"Unsupported series source '{series_source}'.")

    def fetch_metric_summaries(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        metrics: list[SensorMetric],
        provider: str | None,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
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
                recorded_at AS latest_at
            FROM samples
            ORDER BY metric, recorded_at DESC, device_id ASC
        )
        SELECT
            summary.metric,
            latest.latest_value,
            latest.latest_at,
            summary.avg_value,
            summary.min_value,
            summary.max_value,
            summary.sample_count
        FROM summary
        JOIN latest USING (metric)
        ORDER BY summary.metric ASC
        """
        return self._fetch_all(sql, params)

    def _fetch_series_from_raw(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        metrics: list[SensorMetric],
        bucket_interval: str,
        provider: str | None,
    ) -> list[dict[str, Any]]:
        cte_sql, params = self._build_sample_cte(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
            provider=provider,
        )
        sql = f"""
        {cte_sql}
        SELECT
            time_bucket(%s::interval, recorded_at) AS bucket_start,
            metric,
            AVG(value)::double precision AS avg_value,
            MIN(value)::double precision AS min_value,
            MAX(value)::double precision AS max_value,
            COUNT(*)::int AS sample_count
        FROM samples
        GROUP BY bucket_start, metric
        ORDER BY bucket_start ASC, metric ASC
        """
        params.append(bucket_interval)
        return self._fetch_all(sql, params)

    def _fetch_series_from_cagg(
        self,
        *,
        view_name: str,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        metrics: list[SensorMetric],
        bucket_interval: str,
        provider: str | None,
    ) -> list[dict[str, Any]]:
        metric_names = [metric.value for metric in metrics]
        params: list[Any] = [bucket_interval, start_utc, end_utc]
        conditions = [
            "bucket_start >= %s",
            "bucket_start <= %s",
            "source = 'hoogendoorn'",
        ]
        if zone:
            conditions.append("greenhouse_zone = %s")
            params.append(zone)
        if provider:
            conditions.append("provider = %s")
            params.append(provider)
        if metric_names:
            conditions.append("metric = ANY(%s)")
            params.append(metric_names)

        sql = f"""
        SELECT
            time_bucket(%s::interval, bucket_start) AS bucket_start,
            metric,
            (
                SUM(avg_value * sample_count)::double precision
                / NULLIF(SUM(sample_count), 0)
            )::double precision AS avg_value,
            MIN(min_value)::double precision AS min_value,
            MAX(max_value)::double precision AS max_value,
            SUM(sample_count)::int AS sample_count
        FROM {view_name}
        WHERE {' AND '.join(conditions)}
        GROUP BY 1, 2
        ORDER BY 1 ASC, 2 ASC
        """
        return self._fetch_all(sql, params)

    def _build_sample_cte(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        zone: str | None,
        metrics: list[SensorMetric],
        provider: str | None,
    ) -> tuple[str, list[Any]]:
        metric_names = [metric.value for metric in metrics]
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
        if metric_names:
            conditions.append("sample.metric = ANY(%s)")
            params.append(metric_names)

        cte_sql = f"""
        WITH samples AS (
            SELECT
                sensor_data.recorded_at,
                sensor_data.greenhouse_zone,
                sensor_data.device_id,
                sample.metric,
                sample.value::double precision AS value,
                COALESCE(sensor_data.extras->>'provider', '') AS provider,
                COALESCE(sensor_data.extras->>'source', '') AS source,
                sensor_data.extras
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
