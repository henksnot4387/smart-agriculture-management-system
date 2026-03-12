from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.repositories.summary import CopilotSummaryRepository
from app.schemas.copilot import (
    CopilotSummaryResponse,
    DiseaseCountItem,
    SummaryMetricGroup,
    SummaryMetricStats,
)

METRIC_ORDER = ("temperature", "humidity", "ec", "ph")
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "temperature": (10.0, 35.0),
    "humidity": (40.0, 95.0),
    "ec": (1.0, 5.0),
    "ph": (5.0, 7.5),
}
METRIC_LABELS = {
    "temperature": "温度",
    "humidity": "湿度",
    "ec": "EC",
    "ph": "pH",
}
METRIC_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "ec": "mS/cm",
    "ph": "pH",
}


class CopilotSummaryService:
    def __init__(self, settings: Settings, repository: CopilotSummaryRepository):
        self._settings = settings
        self._repository = repository

    def get_summary(
        self,
        *,
        hours: int = 24,
        zone: str | None = None,
        provider: str | None = None,
    ) -> CopilotSummaryResponse:
        bounded_hours = max(1, min(hours, 168))
        resolved_provider = provider or self._settings.hoogendoorn_provider or None
        cached = self._try_read_cache(hours=bounded_hours, zone=zone, provider=resolved_provider)
        if cached is not None:
            return cached

        end_utc = datetime.now(UTC)
        start_utc = end_utc - timedelta(hours=bounded_hours)

        metric_stats = self._repository.fetch_metric_stats(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            provider=resolved_provider,
        )
        metric_anomalies = self._repository.fetch_metric_anomalies(
            start_utc=start_utc,
            end_utc=end_utc,
            zone=zone,
            provider=resolved_provider,
            temperature_low=DEFAULT_THRESHOLDS["temperature"][0],
            temperature_high=DEFAULT_THRESHOLDS["temperature"][1],
            humidity_low=DEFAULT_THRESHOLDS["humidity"][0],
            humidity_high=DEFAULT_THRESHOLDS["humidity"][1],
            ec_low=DEFAULT_THRESHOLDS["ec"][0],
            ec_high=DEFAULT_THRESHOLDS["ec"][1],
            ph_low=DEFAULT_THRESHOLDS["ph"][0],
            ph_high=DEFAULT_THRESHOLDS["ph"][1],
        )
        disease_rows = self._repository.fetch_disease_counts(start_utc=start_utc, end_utc=end_utc)

        metrics = self._build_metric_group(metric_stats, metric_anomalies)
        disease_counts = [DiseaseCountItem(diseaseType=str(row["disease_type"]), count=int(row["total_count"])) for row in disease_rows]
        total_disease_events = sum(item.count for item in disease_counts)
        narrative = self._build_narrative(
            metrics=metrics,
            disease_counts=disease_counts,
            total_disease_events=total_disease_events,
            hours=bounded_hours,
            zone=zone,
        )

        response = CopilotSummaryResponse(
            windowStartUtc=start_utc,
            windowEndUtc=end_utc,
            generatedAtUtc=datetime.now(UTC),
            hours=bounded_hours,
            provider=resolved_provider,
            zone=zone,
            metrics=metrics,
            diseaseCounts=disease_counts,
            totalDiseaseEvents=total_disease_events,
            narrative=narrative,
        )
        self._try_write_cache(response=response)
        return response

    def _try_read_cache(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str | None,
    ) -> CopilotSummaryResponse | None:
        if hours != 24:
            return None
        try:
            cached = self._repository.read_summary_cache(hours=hours, zone=zone, provider=provider)
        except Exception:  # noqa: BLE001
            return None
        if not cached or not isinstance(cached.get("payload"), dict):
            return None
        try:
            generated_at = cached.get("generated_at")
            if isinstance(generated_at, datetime):
                age = datetime.now(UTC) - generated_at.astimezone(UTC)
                if age > timedelta(minutes=15):
                    return None
            return CopilotSummaryResponse(**cached["payload"])
        except Exception:  # noqa: BLE001
            return None

    def _try_write_cache(self, *, response: CopilotSummaryResponse) -> None:
        if response.hours != 24:
            return
        try:
            self._repository.write_summary_cache(
                hours=response.hours,
                zone=response.zone,
                provider=response.provider,
                payload=response.model_dump(mode="json"),
            )
        except Exception:
            # Do not block online summary response when cache persistence fails.
            return

    def _build_metric_group(
        self,
        metric_stats_rows: list[dict[str, Any]],
        anomaly_rows: list[dict[str, Any]],
    ) -> SummaryMetricGroup:
        stats_map = {str(row["metric"]): row for row in metric_stats_rows}
        anomaly_map = {str(row["metric"]): row for row in anomaly_rows}

        payload: dict[str, SummaryMetricStats] = {}
        for metric in METRIC_ORDER:
            thresholds = DEFAULT_THRESHOLDS[metric]
            stats_row = stats_map.get(metric)
            anomaly_row = anomaly_map.get(metric)

            payload[metric] = SummaryMetricStats(
                latest=float(stats_row["latest_value"]) if stats_row and stats_row.get("latest_value") is not None else None,
                avg=float(stats_row["avg_value"]) if stats_row and stats_row.get("avg_value") is not None else None,
                min=float(stats_row["min_value"]) if stats_row and stats_row.get("min_value") is not None else None,
                max=float(stats_row["max_value"]) if stats_row and stats_row.get("max_value") is not None else None,
                sampleCount=int(stats_row["sample_count"]) if stats_row and stats_row.get("sample_count") is not None else 0,
                lowThreshold=thresholds[0],
                highThreshold=thresholds[1],
                anomalousSamples=int(anomaly_row["anomalous_samples"]) if anomaly_row and anomaly_row.get("anomalous_samples") is not None else 0,
                anomalyDurationMinutes=round(
                    (float(anomaly_row["anomaly_seconds"]) if anomaly_row and anomaly_row.get("anomaly_seconds") is not None else 0.0)
                    / 60,
                    2,
                ),
            )

        return SummaryMetricGroup(
            temperature=payload["temperature"],
            humidity=payload["humidity"],
            ec=payload["ec"],
            ph=payload["ph"],
        )

    def _build_narrative(
        self,
        *,
        metrics: SummaryMetricGroup,
        disease_counts: list[DiseaseCountItem],
        total_disease_events: int,
        hours: int,
        zone: str | None,
    ) -> str:
        metric_lines: list[str] = []
        for metric in METRIC_ORDER:
            item = getattr(metrics, metric)
            label = METRIC_LABELS[metric]
            unit = METRIC_UNITS[metric]
            if item.sampleCount == 0 or item.avg is None:
                metric_lines.append(f"{label}暂无有效样本。")
                continue
            metric_lines.append(
                f"{label}均值 {item.avg:.2f}{unit}，区间 {item.min:.2f}~{item.max:.2f}{unit}，"
                f"异常累计 {item.anomalyDurationMinutes:.1f} 分钟（{item.anomalousSamples} 个异常点）。"
            )

        if total_disease_events > 0:
            top = "、".join(f"{item.diseaseType} {item.count}次" for item in disease_counts[:3])
            disease_line = f"病害识别完成 {total_disease_events} 次，主要类型：{top}。"
        else:
            disease_line = "病害识别在该时间窗内暂无完成记录。"

        scope = f"分区 {zone}" if zone else "全场"
        return f"{scope}近{hours}小时摘要：{' '.join(metric_lines)} {disease_line}"
