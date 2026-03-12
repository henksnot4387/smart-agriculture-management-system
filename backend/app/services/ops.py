from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.integrations.hoogendoorn.catalog import load_metric_catalog
from app.repositories.ops import OpsRepository
from app.schemas.ops import (
    MetricCatalogItem,
    OpsCatalogCoverage,
    OpsCatalogResponse,
    OpsLiveMeta,
    OpsLiveResponse,
    OpsMetricValue,
    OpsModuleSnapshot,
    OpsTrendPoint,
    OpsTrendsResponse,
    OpsZoneSnapshot,
)


class OpsService:
    def __init__(self, settings: Settings, repository: OpsRepository):
        self._settings = settings
        self._repository = repository
        self._display_timezone = ZoneInfo("Asia/Shanghai")
        self._catalog = load_metric_catalog()

    def get_catalog(self, *, provider: str | None, lookback_hours: int) -> OpsCatalogResponse:
        resolved_provider = self._resolve_provider(provider)
        bounded_hours = max(1, min(lookback_hours, 168))
        coverage_rows = self._repository.fetch_catalog_coverage(
            provider=resolved_provider,
            lookback_hours=bounded_hours,
        )
        coverage_map = {
            (str(row.get("control_type_id") or ""), str(row.get("parameter_id") or "")): row
            for row in coverage_rows
        }
        items: list[MetricCatalogItem] = []
        covered = 0
        for measurement in self._catalog.measurements:
            coverage = coverage_map.get((measurement.control_type_id, measurement.parameter_id))
            latest_sample_at = coverage.get("latest_sample_at") if coverage else None
            item = MetricCatalogItem(
                controlTypeId=measurement.control_type_id,
                parameterId=measurement.parameter_id,
                controlTypeName=measurement.control_type_name,
                parameterName=measurement.parameter_name,
                metricKey=measurement.metric_key,
                displayName=measurement.display_name,
                module=measurement.module,
                moduleLabel=measurement.module_label,
                area=measurement.area,
                valueType=measurement.value_type,
                unit=measurement.unit,
                canonicalMetric=measurement.canonical_metric,
                covered=bool(coverage),
                latestSampleAtUtc=latest_sample_at,
                latestSampleAtLocal=self._to_local_text(latest_sample_at),
            )
            if item.covered:
                covered += 1
            items.append(item)
        total = len(items)
        coverage_rate = (covered / total) if total else 0.0
        return OpsCatalogResponse(
            version=self._catalog.version,
            source=self._catalog.source,
            systemId=self._catalog.system_id or self._settings.hoogendoorn_system_id,
            provider=resolved_provider,
            coverage=OpsCatalogCoverage(
                total=total,
                covered=covered,
                coverageRate=round(coverage_rate, 4),
                gatePassed=(total > 0 and covered == total),
            ),
            items=items,
        )

    def get_live(self, *, provider: str | None, lookback_hours: int) -> OpsLiveResponse:
        resolved_provider = self._resolve_provider(provider)
        bounded_hours = max(1, min(lookback_hours, 168))
        now_utc = datetime.now(UTC)
        rows = self._repository.fetch_latest_zone_metrics(
            provider=resolved_provider,
            lookback_hours=bounded_hours,
        )
        latest_sample_at = self._repository.fetch_latest_sample_at(provider=resolved_provider)
        freshness_status, warning_message = self._resolve_freshness(
            latest_sample_at=latest_sample_at,
            now_utc=now_utc,
        )

        zone_map: dict[str, OpsZoneSnapshot] = {}
        module_zone_sets: dict[tuple[str, str], set[str]] = {}
        module_metric_counts: dict[tuple[str, str], int] = {}
        for row in rows:
            zone = str(row.get("greenhouse_zone") or "未命名分区")
            zone_item = zone_map.get(zone)
            if zone_item is None:
                zone_item = OpsZoneSnapshot(zone=zone)
                zone_map[zone] = zone_item

            recorded_at = row["recorded_at"]
            metric = OpsMetricValue(
                metricKey=str(row.get("metric_key") or ""),
                displayName=str(row.get("display_name") or row.get("metric_key") or ""),
                value=float(row.get("value") or 0.0),
                unit=str(row.get("unit") or "raw"),
                valueType=str(row.get("value_type") or "numeric"),
                module=str(row.get("module") or "other"),
                moduleLabel=str(row.get("module_label") or "其他"),
                area=str(row.get("area") or "utility"),
                recordedAtUtc=recorded_at,
                recordedAtLocal=self._to_local_text(recorded_at) or "--",
            )
            zone_item.metrics.append(metric)
            latest_in_zone = zone_item.latestSampleAtUtc
            if latest_in_zone is None or recorded_at > latest_in_zone:
                zone_item.latestSampleAtUtc = recorded_at
                zone_item.latestSampleAtLocal = self._to_local_text(recorded_at)

            module_key = (metric.module, metric.moduleLabel)
            module_zone_sets.setdefault(module_key, set()).add(zone)
            module_metric_counts[module_key] = module_metric_counts.get(module_key, 0) + 1

        modules = [
            OpsModuleSnapshot(
                module=module,
                moduleLabel=module_label,
                zoneCount=len(zone_set),
                metricCount=module_metric_counts.get((module, module_label), 0),
            )
            for (module, module_label), zone_set in module_zone_sets.items()
        ]
        modules.sort(key=lambda item: item.module)

        zones = list(zone_map.values())
        zones.sort(key=lambda item: item.zone)
        for zone in zones:
            zone.metrics.sort(key=lambda metric: (metric.module, metric.metricKey))

        return OpsLiveResponse(
            meta=OpsLiveMeta(
                provider=resolved_provider,
                lookbackHours=bounded_hours,
                pageRefreshedAt=now_utc,
                latestSampleAtUtc=latest_sample_at,
                latestSampleAtLocal=self._to_local_text(latest_sample_at),
                freshnessStatus=freshness_status,
                warningMessage=warning_message,
            ),
            zones=zones,
            modules=modules,
        )

    def get_trends(
        self,
        *,
        provider: str | None,
        hours: int,
        zone: str | None,
    ) -> OpsTrendsResponse:
        resolved_provider = self._resolve_provider(provider)
        bounded_hours = max(1, min(hours, 168))
        end_utc = datetime.now(UTC)
        start_utc = end_utc - timedelta(hours=bounded_hours)
        rows = self._repository.fetch_trend_points(
            provider=resolved_provider,
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
        )
        points = [
            OpsTrendPoint(
                metricKey=str(row.get("metric_key") or ""),
                displayName=str(row.get("display_name") or row.get("metric_key") or ""),
                module=str(row.get("module") or "other"),
                moduleLabel=str(row.get("module_label") or "其他"),
                bucketStartUtc=row["bucket_start"],
                bucketStartLocal=self._to_local_text(row["bucket_start"]) or "--",
                avg=float(row.get("avg_value") or 0.0),
                min=float(row.get("min_value") or 0.0),
                max=float(row.get("max_value") or 0.0),
                count=int(row.get("sample_count") or 0),
            )
            for row in rows
        ]
        return OpsTrendsResponse(
            provider=resolved_provider,
            startUtc=start_utc,
            endUtc=end_utc,
            zone=zone,
            points=points,
        )

    def _resolve_provider(self, provider: str | None) -> str:
        cleaned = (provider or "").strip()
        if cleaned:
            return cleaned
        return "partner_api"

    def _resolve_freshness(self, *, latest_sample_at: datetime | None, now_utc: datetime) -> tuple[str, str | None]:
        if latest_sample_at is None:
            return "STALE", "当前没有可用的 partner_api 最新样本。"
        lag_minutes = (now_utc - latest_sample_at.astimezone(UTC)).total_seconds() / 60
        if lag_minutes > 30:
            return "STALE", f"数据最新采样时间距今 {lag_minutes:.1f} 分钟，超过 30 分钟门禁。"
        if lag_minutes > 10:
            return "WARNING", f"数据最新采样时间距今 {lag_minutes:.1f} 分钟，建议检查链路。"
        return "FRESH", None

    def _to_local_text(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(self._display_timezone).strftime("%Y-%m-%d %H:%M:%S")
