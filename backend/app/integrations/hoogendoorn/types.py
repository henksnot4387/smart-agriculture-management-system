from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MeasurementDefinition:
    metric_key: str
    control_type_id: str
    parameter_id: str
    control_type_name: str
    parameter_name: str
    module: str
    module_label: str
    area: str
    value_type: str
    unit: str
    display_name: str
    canonical_metric: str | None = None


@dataclass(frozen=True)
class ControlInstance:
    type_id: str
    instance_id: str
    instance_name: str


@dataclass(frozen=True)
class SensorPoint:
    metric_key: str
    control_type_id: str
    parameter_id: str
    control_type_name: str
    parameter_name: str
    instance_id: str
    instance_name: str
    recorded_at: datetime
    utc_offset_minutes: int
    value: float
    module: str
    module_label: str
    area: str
    value_type: str
    unit: str
    display_name: str
    canonical_metric: str | None = None
