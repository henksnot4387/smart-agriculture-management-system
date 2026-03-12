from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.integrations.hoogendoorn.types import ControlInstance, MeasurementDefinition, SensorPoint


class HoogendoornProvider(ABC):
    provider_name: str

    @abstractmethod
    async def fetch_control_instances(
        self,
        system_id: str,
        control_type_id: str,
    ) -> list[ControlInstance]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_series(
        self,
        system_id: str,
        measurement: MeasurementDefinition,
        instances: list[ControlInstance],
        start: datetime,
        end: datetime,
    ) -> list[SensorPoint]:
        raise NotImplementedError

    async def get_runtime_status(self) -> dict[str, object]:
        return {"provider": self.provider_name}
