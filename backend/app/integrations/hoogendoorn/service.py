from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from uuid import NAMESPACE_URL, uuid5

from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings
from app.integrations.hoogendoorn.catalog import load_metric_catalog
from app.integrations.hoogendoorn.exceptions import TemporaryHoogendoornError
from app.integrations.hoogendoorn.provider import HoogendoornProvider
from app.integrations.hoogendoorn.repository import SensorDataRepository
from app.integrations.hoogendoorn.types import ControlInstance, MeasurementDefinition, SensorPoint

logger = logging.getLogger("app.integrations.hoogendoorn.service")


class HoogendoornSyncService:
    def __init__(
        self,
        settings: Settings,
        provider: HoogendoornProvider,
        repository: SensorDataRepository,
    ):
        self._settings = settings
        self._provider = provider
        self._repository = repository
        self._catalog = load_metric_catalog()
        self._measurements = list(self._catalog.measurements)
        self._control_type_measurements: dict[str, list[MeasurementDefinition]] = {}
        for measurement in self._measurements:
            self._control_type_measurements.setdefault(measurement.control_type_id, []).append(measurement)

    @property
    def provider(self) -> HoogendoornProvider:
        return self._provider

    async def sync(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        lookback_minutes: int | None = None,
    ) -> dict[str, object]:
        sync_end = (end or datetime.now(UTC)).astimezone(UTC)
        last_recorded_at = await asyncio.to_thread(
            self._repository.latest_recorded_at,
            self._provider.provider_name,
        )

        if start is not None:
            sync_start = start.astimezone(UTC)
            mode = "manual"
        elif last_recorded_at is not None:
            sync_start = last_recorded_at.astimezone(UTC) - timedelta(
                minutes=self._settings.hoogendoorn_sync_overlap_minutes
            )
            mode = "catch-up"
        else:
            sync_start = sync_end - timedelta(
                minutes=lookback_minutes or self._settings.hoogendoorn_sync_window_minutes
            )
            mode = "bootstrap"

        if sync_start >= sync_end:
            sync_start = sync_end - timedelta(minutes=1)

        all_points: list[SensorPoint] = []
        retries: dict[str, int] = {}
        control_instances_cache: dict[str, list[ControlInstance]] = {}

        for measurement in self._measurements:
            if measurement.control_type_id in control_instances_cache:
                instances = control_instances_cache[measurement.control_type_id]
                instance_attempts = 1
            else:
                instances, instance_attempts = await self._run_with_retry(
                    f"control-instances:{measurement.metric_key}",
                    self._provider.fetch_control_instances,
                    self._settings.hoogendoorn_system_id,
                    measurement.control_type_id,
                )
                control_instances_cache[measurement.control_type_id] = instances
            retries[f"{measurement.metric_key}_control_instances"] = instance_attempts

            if not instances:
                continue

            points, series_attempts = await self._run_with_retry(
                f"series:{measurement.metric_key}",
                self._provider.fetch_series,
                self._settings.hoogendoorn_system_id,
                measurement,
                instances,
                sync_start,
                sync_end,
            )
            retries[f"{measurement.metric_key}_series"] = series_attempts
            all_points.extend(points)

        rows = self._build_sensor_rows(all_points)
        metric_rows = self._build_metric_rows(all_points)
        rows_written = await asyncio.to_thread(self._repository.upsert_sensor_rows, rows)
        metric_rows_written = await asyncio.to_thread(self._repository.upsert_metric_rows, metric_rows)
        latest_synced_at = max((row["recorded_at"] for row in rows), default=last_recorded_at)

        return {
            "provider": self._provider.provider_name,
            "system_id": self._settings.hoogendoorn_system_id,
            "catalog_version": self._catalog.version,
            "catalog_measurement_count": len(self._measurements),
            "mode": mode,
            "start": sync_start.isoformat(),
            "end": sync_end.isoformat(),
            "points_fetched": len(all_points),
            "rows_written": rows_written,
            "metric_rows_written": metric_rows_written,
            "latest_recorded_at": latest_synced_at.isoformat() if latest_synced_at else None,
            "retry_attempts": retries,
        }

    async def status(self) -> dict[str, object]:
        latest_recorded_at = await asyncio.to_thread(
            self._repository.latest_recorded_at,
            self._provider.provider_name,
        )
        runtime_status = await self._provider.get_runtime_status()
        return {
            "provider": self._provider.provider_name,
            "system_id": self._settings.hoogendoorn_system_id,
            "latest_recorded_at": latest_recorded_at.isoformat() if latest_recorded_at else None,
            "catalog_version": self._catalog.version,
            "measurements": [measurement.metric_key for measurement in self._measurements],
            "runtime": runtime_status,
        }

    async def _run_with_retry(self, operation: str, func, *args):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._settings.hoogendoorn_retry_attempts),
            wait=wait_exponential(
                min=self._settings.hoogendoorn_retry_min_seconds,
                max=self._settings.hoogendoorn_retry_max_seconds,
            ),
            retry=retry_if_exception_type(TemporaryHoogendoornError),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                result = await func(*args)
                return result, attempt.retry_state.attempt_number

    def _build_sensor_rows(self, points: list[SensorPoint]) -> list[dict[str, object]]:
        rows: dict[tuple[str, datetime], dict[str, object]] = {}

        for point in points:
            recorded_at = point.recorded_at.astimezone(UTC)
            key = (point.instance_id, recorded_at)
            row = rows.setdefault(
                key,
                {
                    "recorded_at": recorded_at,
                    "id": str(
                        uuid5(
                            NAMESPACE_URL,
                            f"hoogendoorn:{self._settings.hoogendoorn_system_id}:{point.instance_id}:{recorded_at.isoformat()}",
                        )
                    ),
                    "greenhouse_zone": point.instance_name,
                    "device_id": point.instance_id,
                    "temperature": None,
                    "humidity": None,
                    "ec": None,
                    "ph": None,
                    "extras": {
                        "source": "hoogendoorn",
                        "provider": self._provider.provider_name,
                        "system_id": self._settings.hoogendoorn_system_id,
                        "instance_name": point.instance_name,
                        # recorded_at is stored in UTC. utc_offset_minutes is retained only
                        # for rendering and traceability back to the partner payload.
                        "measurements": {},
                    },
                },
            )
            if point.canonical_metric in {"temperature", "humidity", "ec", "ph"}:
                row[point.canonical_metric] = point.value
            row["extras"]["measurements"][point.metric_key] = {
                "control_type_id": point.control_type_id,
                "control_type_name": point.control_type_name,
                "parameter_id": point.parameter_id,
                "parameter_name": point.parameter_name,
                "utc_offset_minutes": point.utc_offset_minutes,
                "module": point.module,
                "module_label": point.module_label,
                "area": point.area,
                "value_type": point.value_type,
                "unit": point.unit,
                "display_name": point.display_name,
            }

        return list(rows.values())

    def _build_metric_rows(self, points: list[SensorPoint]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for point in points:
            recorded_at = point.recorded_at.astimezone(UTC)
            rows.append(
                {
                    "recorded_at": recorded_at,
                    "sample_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            (
                                f"hoogendoorn:{self._settings.hoogendoorn_system_id}:{point.instance_id}:"
                                f"{point.metric_key}:{recorded_at.isoformat()}"
                            ),
                        )
                    ),
                    "greenhouse_zone": point.instance_name,
                    "device_id": point.instance_id,
                    "metric_key": point.metric_key,
                    "display_name": point.display_name,
                    "module": point.module,
                    "module_label": point.module_label,
                    "area": point.area,
                    "value_type": point.value_type,
                    "unit": point.unit,
                    "value": point.value,
                    "source": "hoogendoorn",
                    "provider": self._provider.provider_name,
                    "extras": {
                        "control_type_id": point.control_type_id,
                        "control_type_name": point.control_type_name,
                        "parameter_id": point.parameter_id,
                        "parameter_name": point.parameter_name,
                        "system_id": self._settings.hoogendoorn_system_id,
                        "utc_offset_minutes": point.utc_offset_minutes,
                        "canonical_metric": point.canonical_metric,
                    },
                }
            )
        return rows
