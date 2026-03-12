from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.core.config import Settings
from app.repositories.sensor import (
    SERIES_SOURCE_15M,
    SERIES_SOURCE_1D,
    SERIES_SOURCE_RAW,
    SensorQueryRepository,
)
from app.schemas.sensor import (
    MetricSeriesPoint,
    MetricSummary,
    MetricSummaryGroup,
    RawSensorSample,
    SensorBucket,
    SensorDashboardMeta,
    SensorDashboardResponse,
    SensorMetric,
    SensorRange,
    SensorRawResponse,
    SensorSeriesGroup,
    SensorSeriesResponse,
)

DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")
BUCKET_TO_INTERVAL = {
    SensorBucket.FIVE_MINUTES: "5 minutes",
    SensorBucket.FIFTEEN_MINUTES: "15 minutes",
    SensorBucket.ONE_HOUR: "1 hour",
    SensorBucket.SIX_HOURS: "6 hours",
    SensorBucket.ONE_DAY: "1 day",
}
VALID_METRICS = {metric.value: metric for metric in SensorMetric}
DOWNSAMPLE_15M_THRESHOLD = timedelta(hours=24)
DOWNSAMPLE_1D_THRESHOLD = timedelta(days=30)


class SensorQueryService:
    def __init__(self, settings: Settings, repository: SensorQueryRepository):
        self._settings = settings
        self._repository = repository

    def get_raw(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        zone: str | None,
        metrics_query: str | None,
        limit: int,
        provider: str | None,
    ) -> SensorRawResponse:
        start_utc, end_utc = self._resolve_explicit_window(start, end)
        metrics = self._parse_metrics(metrics_query)
        resolved_provider = self._resolve_provider(provider)
        rows = self._repository.fetch_raw_samples(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
            limit=limit,
            provider=resolved_provider,
        )
        items = [self._build_raw_sample(row) for row in rows]
        return SensorRawResponse(
            startUtc=start_utc,
            endUtc=end_utc,
            zone=zone,
            provider=resolved_provider,
            metrics=metrics,
            items=items,
        )

    def get_series(
        self,
        *,
        range_query: SensorRange | None,
        start: datetime | None,
        end: datetime | None,
        zone: str | None,
        metrics_query: str | None,
        bucket_query: SensorBucket,
        provider: str | None,
    ) -> SensorSeriesResponse:
        start_utc, end_utc, resolved_range = self._resolve_series_window(range_query, start, end)
        metrics = self._parse_metrics(metrics_query)
        bucket = self._resolve_bucket(bucket_query, start_utc, end_utc, resolved_range)
        series_source, bucket = self._resolve_series_source_and_bucket(
            bucket=bucket,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        resolved_provider = self._resolve_provider(provider)
        rows = self._repository.fetch_series_points(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
            bucket_interval=BUCKET_TO_INTERVAL[bucket],
            provider=resolved_provider,
            series_source=series_source,
        )
        return SensorSeriesResponse(
            range=resolved_range,
            bucket=bucket,
            zone=zone,
            provider=resolved_provider,
            metrics=metrics,
            series=self._build_series_group(rows),
        )

    def get_dashboard(
        self,
        *,
        range_query: SensorRange,
        zone: str | None,
        provider: str | None,
    ) -> SensorDashboardResponse:
        start_utc, end_utc, _ = self._resolve_series_window(range_query, None, None)
        metrics = list(SensorMetric)
        bucket = self._resolve_bucket(SensorBucket.AUTO, start_utc, end_utc, range_query.value)
        series_source, bucket = self._resolve_series_source_and_bucket(
            bucket=bucket,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        resolved_provider = self._resolve_provider(provider)
        series_rows = self._repository.fetch_series_points(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
            bucket_interval=BUCKET_TO_INTERVAL[bucket],
            provider=resolved_provider,
            series_source=series_source,
        )
        summary_rows = self._repository.fetch_metric_summaries(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            metrics=metrics,
            provider=resolved_provider,
        )
        return SensorDashboardResponse(
            summary=self._build_summary_group(summary_rows),
            series=self._build_series_group(series_rows),
            meta=SensorDashboardMeta(
                range=range_query,
                bucket=bucket,
                zone=zone,
                provider=resolved_provider,
            ),
        )

    def _resolve_explicit_window(self, start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
        if start is None or end is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start and end are required and must include a timezone offset.",
            )
        start_utc = self._normalize_public_datetime("start", start)
        end_utc = self._normalize_public_datetime("end", end)
        self._validate_window(start_utc, end_utc)
        return start_utc, end_utc

    def _resolve_series_window(
        self,
        range_query: SensorRange | None,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[datetime, datetime, str]:
        if range_query is not None and (start is not None or end is not None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Use either range or start/end, not both.",
            )
        if range_query is not None:
            end_utc = datetime.now(UTC)
            if range_query == SensorRange.LAST_24_HOURS:
                start_utc = end_utc - timedelta(hours=24)
            else:
                start_utc = end_utc - timedelta(days=7)
            return start_utc, end_utc, range_query.value
        start_utc, end_utc = self._resolve_explicit_window(start, end)
        return start_utc, end_utc, "custom"

    def _normalize_public_datetime(self, field_name: str, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} must include a timezone offset or Z suffix.",
            )
        return value.astimezone(UTC)

    def _validate_window(self, start_utc: datetime, end_utc: datetime) -> None:
        if start_utc > end_utc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start must be earlier than or equal to end.",
            )

    def _parse_metrics(self, metrics_query: str | None) -> list[SensorMetric]:
        if not metrics_query:
            return list(SensorMetric)

        metrics: list[SensorMetric] = []
        seen: set[SensorMetric] = set()
        for raw_metric in metrics_query.split(","):
            metric_name = raw_metric.strip().lower()
            if not metric_name:
                continue
            metric = VALID_METRICS.get(metric_name)
            if metric is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unsupported metric '{raw_metric.strip()}'. Allowed values: temperature, humidity, ec, ph.",
                )
            if metric not in seen:
                metrics.append(metric)
                seen.add(metric)

        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="metrics must contain at least one supported metric.",
            )
        return metrics

    def _resolve_provider(self, provider: str | None) -> str | None:
        if provider:
            return provider
        # Default to the active Hoogendoorn provider so dashboards do not mix
        # mock rows with real partner_api rows in the same environment.
        return self._settings.hoogendoorn_provider or None

    def _resolve_bucket(
        self,
        bucket_query: SensorBucket,
        start_utc: datetime,
        end_utc: datetime,
        resolved_range: str,
    ) -> SensorBucket:
        if bucket_query != SensorBucket.AUTO:
            return bucket_query
        if resolved_range == SensorRange.LAST_24_HOURS.value:
            return SensorBucket.FIFTEEN_MINUTES
        if resolved_range == SensorRange.LAST_7_DAYS.value:
            return SensorBucket.ONE_HOUR

        duration = end_utc - start_utc
        if duration <= timedelta(hours=6):
            return SensorBucket.FIVE_MINUTES
        if duration <= timedelta(hours=24):
            return SensorBucket.FIFTEEN_MINUTES
        if duration <= timedelta(days=7):
            return SensorBucket.ONE_HOUR
        if duration <= DOWNSAMPLE_1D_THRESHOLD:
            return SensorBucket.SIX_HOURS
        return SensorBucket.ONE_DAY

    def _resolve_series_source_and_bucket(
        self,
        *,
        bucket: SensorBucket,
        start_utc: datetime,
        end_utc: datetime,
    ) -> tuple[str, SensorBucket]:
        duration = end_utc - start_utc

        if duration > DOWNSAMPLE_1D_THRESHOLD:
            if bucket != SensorBucket.ONE_DAY:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="For ranges longer than 30 days, bucket must be 1d.",
                )
            return SERIES_SOURCE_1D, bucket

        if duration > DOWNSAMPLE_15M_THRESHOLD:
            if bucket == SensorBucket.FIVE_MINUTES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="For ranges longer than 24 hours, bucket cannot be 5m.",
                )
            return SERIES_SOURCE_15M, bucket

        return SERIES_SOURCE_RAW, bucket

    def _build_raw_sample(self, row: dict[str, object]) -> RawSensorSample:
        recorded_at = row["recorded_at"]
        extras = row.get("extras") or {}
        metric = SensorMetric(str(row["metric"]))
        offset = self._resolve_utc_offset_minutes(extras, metric)
        return RawSensorSample(
            recordedAtUtc=recorded_at,
            recordedAtLocal=self._to_local(recorded_at),
            utcOffsetMinutes=offset,
            zone=str(row["greenhouse_zone"]),
            deviceId=str(row["device_id"]),
            metric=metric,
            value=float(row["value"]),
            provider=str(row["provider"]) if row.get("provider") else None,
            source=str(row["source"]) if row.get("source") else None,
            extras=extras,
        )

    def _build_series_group(self, rows: list[dict[str, object]]) -> SensorSeriesGroup:
        group = SensorSeriesGroup()
        for row in rows:
            bucket_start = row["bucket_start"]
            point = MetricSeriesPoint(
                bucketStartUtc=bucket_start,
                bucketStartLocal=self._to_local(bucket_start),
                avg=float(row["avg_value"]),
                min=float(row["min_value"]),
                max=float(row["max_value"]),
                count=int(row["sample_count"]),
            )
            getattr(group, str(row["metric"])).append(point)
        return group

    def _build_summary_group(self, rows: list[dict[str, object]]) -> MetricSummaryGroup:
        summary = MetricSummaryGroup()
        for row in rows:
            latest_at = row["latest_at"]
            metric_summary = MetricSummary(
                latest=float(row["latest_value"]),
                latestAtUtc=latest_at,
                latestAtLocal=self._to_local(latest_at),
                avg=float(row["avg_value"]),
                min=float(row["min_value"]),
                max=float(row["max_value"]),
                sampleCount=int(row["sample_count"]),
            )
            setattr(summary, str(row["metric"]), metric_summary)
        return summary

    def _resolve_utc_offset_minutes(self, extras: dict[str, object], metric: SensorMetric) -> int:
        measurements = extras.get("measurements")
        if isinstance(measurements, dict):
            metric_payload = measurements.get(metric.value)
            if isinstance(metric_payload, dict):
                for key in ("utc_offset_minutes", "utcOffsetMinutes", "utcOffset"):
                    value = metric_payload.get(key)
                    if value is not None:
                        return int(value)
        return int(self._to_local(datetime.now(UTC)).utcoffset().total_seconds() // 60)

    def _to_local(self, value: datetime) -> datetime:
        return value.astimezone(DISPLAY_TIMEZONE)
