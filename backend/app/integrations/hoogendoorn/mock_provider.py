from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math
from uuid import uuid5, NAMESPACE_URL

from app.core.config import Settings
from app.integrations.hoogendoorn.exceptions import TemporaryHoogendoornError
from app.integrations.hoogendoorn.provider import HoogendoornProvider
from app.integrations.hoogendoorn.types import ControlInstance, MeasurementDefinition, SensorPoint


class MockHoogendoornProvider(HoogendoornProvider):
    provider_name = "mock"

    def __init__(self, settings: Settings):
        self._settings = settings
        self._failures_remaining = settings.hoogendoorn_mock_failures_before_success

    def set_failures_remaining(self, count: int) -> int:
        self._failures_remaining = max(count, 0)
        return self._failures_remaining

    def _consume_failure(self) -> None:
        if self._failures_remaining > 0:
            self._failures_remaining -= 1
            raise TemporaryHoogendoornError(
                f"Mock outage simulated, failures remaining: {self._failures_remaining}"
            )

    async def fetch_control_instances(
        self,
        system_id: str,
        control_type_id: str,
    ) -> list[ControlInstance]:
        self._consume_failure()
        instances: list[ControlInstance] = []
        for zone in range(1, self._settings.hoogendoorn_mock_zone_count + 1):
            zone_name = f"Greenhouse {zone:02d}"
            instance_id = str(uuid5(NAMESPACE_URL, f"{system_id}:{control_type_id}:{zone_name}"))
            instances.append(
                ControlInstance(
                    type_id=control_type_id,
                    instance_id=instance_id,
                    instance_name=zone_name,
                )
            )
        return instances

    async def fetch_series(
        self,
        system_id: str,
        measurement: MeasurementDefinition,
        instances: list[ControlInstance],
        start: datetime,
        end: datetime,
    ) -> list[SensorPoint]:
        self._consume_failure()
        points: list[SensorPoint] = []
        interval = timedelta(minutes=self._settings.hoogendoorn_mock_interval_minutes)
        cursor = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)

        while cursor <= end_utc:
            for index, instance in enumerate(instances, start=1):
                points.append(
                    SensorPoint(
                        metric_key=measurement.metric_key,
                        control_type_id=measurement.control_type_id,
                        parameter_id=measurement.parameter_id,
                        control_type_name=measurement.control_type_name,
                        parameter_name=measurement.parameter_name,
                        instance_id=instance.instance_id,
                        instance_name=instance.instance_name,
                        recorded_at=cursor,
                        utc_offset_minutes=480,
                        value=self._generate_value(
                            measurement.metric_key,
                            measurement.canonical_metric,
                            index,
                            cursor,
                        ),
                        module=measurement.module,
                        module_label=measurement.module_label,
                        area=measurement.area,
                        value_type=measurement.value_type,
                        unit=measurement.unit,
                        display_name=measurement.display_name,
                        canonical_metric=measurement.canonical_metric,
                    )
                )
            cursor += interval

        return points

    async def get_runtime_status(self) -> dict[str, object]:
        return {
            "provider": self.provider_name,
            "failures_remaining": self._failures_remaining,
            "zone_count": self._settings.hoogendoorn_mock_zone_count,
            "interval_minutes": self._settings.hoogendoorn_mock_interval_minutes,
        }

    def _generate_value(
        self,
        metric_key: str,
        canonical_metric: str | None,
        zone_index: int,
        recorded_at: datetime,
    ) -> float:
        wave = math.sin(recorded_at.timestamp() / 1800 + zone_index)
        if canonical_metric == "temperature":
            return round(21.5 + zone_index * 0.4 + wave * 1.8, 2)
        if canonical_metric == "humidity":
            return round(68 + zone_index * 1.2 + wave * 6, 2)
        if canonical_metric == "ec":
            return round(2.1 + zone_index * 0.08 + wave * 0.12, 2)
        if canonical_metric == "ph":
            return round(5.7 + zone_index * 0.03 + wave * 0.06, 2)
        normalized = metric_key.lower()
        if "co2" in normalized:
            return round(520 + zone_index * 10 + wave * 45, 2)
        if "wind_speed" in normalized:
            return round(2.5 + zone_index * 0.1 + wave * 0.8, 2)
        if "wind_direction" in normalized:
            return round((180 + zone_index * 5 + wave * 90) % 360, 2)
        if "position" in normalized or "setpoint" in normalized or "actuation" in normalized:
            return round(max(0.0, min(100.0, 55 + wave * 30)), 2)
        if "active" in normalized or "status" in normalized or "on_detection" in normalized:
            return 1.0 if wave > -0.2 else 0.0
        if "radiation" in normalized:
            return round(max(0.0, 350 + wave * 280), 2)
        if "rain" in normalized:
            return round(max(0.0, wave * 3), 2)
        return round(10 + zone_index + wave * 2, 2)
