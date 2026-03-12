from __future__ import annotations

import json
from dataclasses import dataclass
import os
from pathlib import Path

from app.core.config import REPO_ROOT
from app.integrations.hoogendoorn.types import MeasurementDefinition

DEFAULT_PRIVATE_CATALOG_PATH = REPO_ROOT / "backend" / "data" / "hoogendoorn_metric_catalog.private.json"
DEFAULT_EXAMPLE_CATALOG_PATH = REPO_ROOT / "backend" / "data" / "hoogendoorn_metric_catalog.example.json"
LEGACY_PUBLIC_CATALOG_PATH = REPO_ROOT / "backend" / "data" / "hoogendoorn_metric_catalog.json"


@dataclass(frozen=True)
class HoogendoornMetricCatalog:
    version: str
    system_id: str
    source: str
    measurements: tuple[MeasurementDefinition, ...]


def _resolve_catalog_path() -> Path:
    explicit_path = (os.getenv("HOOGENDOORN_METRIC_CATALOG_PATH") or "").strip()
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    candidates.extend(
        [
            DEFAULT_PRIVATE_CATALOG_PATH,
            DEFAULT_EXAMPLE_CATALOG_PATH,
            LEGACY_PUBLIC_CATALOG_PATH,
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return DEFAULT_EXAMPLE_CATALOG_PATH


def load_metric_catalog() -> HoogendoornMetricCatalog:
    catalog_path = _resolve_catalog_path()
    if not catalog_path.exists():
        raise FileNotFoundError(f"Hoogendoorn metric catalog is missing: {catalog_path}")

    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    measurements: list[MeasurementDefinition] = []
    for item in payload.get("items", []):
        if not bool(item.get("enabled", True)):
            continue
        parameter_name = str(item.get("parameterName") or "").strip()
        canonical_metric = (
            (str(item.get("canonicalMetric")).strip() or None)
            if item.get("canonicalMetric") is not None
            else None
        )
        parameter_name_lower = parameter_name.lower()
        if canonical_metric and any(
            token in parameter_name_lower
            for token in (
                "setpoint",
                "status",
                "active",
                "activated",
                "reason",
                "position",
                "demand",
                "sum",
                "number of starts",
                "computed",
                "actuation",
            )
        ):
            canonical_metric = None
        measurements.append(
            MeasurementDefinition(
                metric_key=str(item.get("metricKey") or "").strip(),
                control_type_id=str(item.get("controlTypeId") or "").strip(),
                parameter_id=str(item.get("parameterId") or "").strip(),
                control_type_name=str(item.get("controlTypeName") or "").strip(),
                parameter_name=parameter_name,
                module=str(item.get("module") or "other").strip(),
                module_label=str(item.get("moduleLabel") or "其他").strip(),
                area=str(item.get("area") or "utility").strip(),
                value_type=str(item.get("valueType") or "numeric").strip(),
                unit=str(item.get("unit") or "raw").strip(),
                display_name=str(item.get("displayName") or item.get("parameterName") or "").strip(),
                canonical_metric=canonical_metric,
            )
        )
    measurements = [
        measurement
        for measurement in measurements
        if measurement.metric_key and measurement.control_type_id and measurement.parameter_id
    ]
    return HoogendoornMetricCatalog(
        version=str(payload.get("version") or ""),
        source=str(payload.get("source") or ""),
        system_id=str(payload.get("systemId") or ""),
        measurements=tuple(measurements),
    )
