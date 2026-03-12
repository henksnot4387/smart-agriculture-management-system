from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings
from app.repositories.ai_insights import AIInsightsRepository
from app.repositories.knowledge import LocalKnowledgeRepository
from app.schemas.ai_insights import (
    AIInsightAnomalyTimelineItem,
    AIInsightConfirmedTask,
    AIInsightDataEvidence,
    AIInsightDraftItem,
    AIInsightExecutive,
    AIInsightExpertItem,
    AIInsightKnowledgeEvidence,
    AIInsightRecommendationConfirmResponse,
    AIInsightRecommendationGenerateResponse,
    AIInsightRecommendationListResponse,
    AIInsightSummaryMeta,
    AIInsightSummaryResponse,
    AIInsightTrendPoint,
    AIInsightVisual,
    AIInsightZoneRiskItem,
)

DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "temperature": (10.0, 35.0),
    "humidity": (40.0, 95.0),
    "ec": (1.0, 5.0),
    "ph": (5.0, 7.5),
}
METRIC_ORDER = ("temperature", "humidity", "ec", "ph")
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


@dataclass(slots=True)
class _MetricSnapshot:
    metric: str
    avg: float | None
    min: float | None
    max: float | None
    latest: float | None
    sample_count: int
    anomaly_minutes: float
    anomalous_samples: int


@dataclass(slots=True)
class _AnalysisResult:
    executive: AIInsightExecutive
    expert_items: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    llm_provider: str
    llm_model: str | None
    fallback_used: bool


class AIInsightsService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: AIInsightsRepository,
        knowledge_repository: LocalKnowledgeRepository,
    ):
        self._settings = settings
        self._repository = repository
        self._knowledge_repository = knowledge_repository
        self._display_timezone = ZoneInfo("Asia/Shanghai")

    def get_summary(
        self,
        *,
        hours: int,
        zone: str | None,
        mode: str,
        provider: str | None,
    ) -> AIInsightSummaryResponse:
        bounded_hours = max(1, min(hours, 168))
        resolved_zone = self._normalize_zone(zone)
        resolved_provider = self._resolve_provider(provider)
        normalized_mode = "refresh" if mode == "refresh" else "cached"

        if normalized_mode == "cached":
            cached = self._repository.read_latest_summary_run(
                hours=bounded_hours,
                zone=resolved_zone,
                provider=resolved_provider,
            )
            if cached and isinstance(cached.get("payload"), dict):
                try:
                    payload = dict(cached["payload"])
                    meta = payload.get("meta")
                    if isinstance(meta, dict):
                        meta["pageRefreshedAt"] = datetime.now(UTC).isoformat()
                    payload["recommendationDrafts"] = [
                        item.model_dump(mode="json")
                        for item in self._list_pending_drafts(limit=20)
                    ]
                    return AIInsightSummaryResponse(**payload)
                except Exception:  # noqa: BLE001
                    pass

        return self._generate_summary(hours=bounded_hours, zone=resolved_zone, provider=resolved_provider, mode=normalized_mode)

    def generate_recommendations(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str | None,
        instruction: str | None,
        max_items: int | None,
    ) -> AIInsightRecommendationGenerateResponse:
        summary = self.get_summary(hours=hours, zone=zone, mode="refresh", provider=provider)
        if summary.meta.freshnessStatus == "STALE":
            raise ValueError("partner_api 数据已超过 30 分钟未更新，禁止生成新建议。")

        resolved_zone = self._normalize_zone(zone)
        resolved_provider = self._resolve_provider(provider)
        resolved_max_items = max(1, min(max_items or self._settings.copilot_recommendation_max_items, 10))
        knowledge_refs = self._select_knowledge_refs_from_summary(summary=summary, limit=8)

        generated = self._generate_recommendation_content(
            summary=summary,
            knowledge_refs=knowledge_refs,
            instruction=instruction,
            max_items=resolved_max_items,
        )

        latest_run = self._repository.read_latest_summary_run(
            hours=max(1, min(hours, 168)),
            zone=resolved_zone,
            provider=resolved_provider,
        )
        summary_run_id = int(latest_run["id"]) if latest_run and latest_run.get("id") is not None else None
        rows = self._repository.create_recommendation_drafts(
            summary_run_id=summary_run_id,
            hours=max(1, min(hours, 168)),
            zone=resolved_zone,
            provider=resolved_provider,
            llm_provider=generated.llm_provider,
            llm_model=generated.llm_model,
            fallback_used=generated.fallback_used,
            drafts=generated.recommendations,
        )

        return AIInsightRecommendationGenerateResponse(
            generatedAtUtc=datetime.now(UTC),
            hours=max(1, min(hours, 168)),
            zone=resolved_zone,
            provider=resolved_provider,
            llmProvider=generated.llm_provider,
            llmModel=generated.llm_model,
            fallbackUsed=generated.fallback_used,
            recommendations=[self._row_to_draft_item(row) for row in rows],
        )

    def list_recommendations(
        self,
        *,
        limit: int,
        status: str | None,
    ) -> AIInsightRecommendationListResponse:
        bounded_limit = max(1, min(limit, 100))
        normalized_status = status if status in {"PENDING", "CONFIRMED"} else None
        total, rows = self._repository.list_recommendation_drafts(limit=bounded_limit, status=normalized_status)
        return AIInsightRecommendationListResponse(
            total=total,
            limit=bounded_limit,
            status=normalized_status,
            items=[self._row_to_draft_item(row) for row in rows],
        )

    def confirm_recommendations(
        self,
        *,
        draft_ids: list[str],
        confirmed_by_id: str,
    ) -> AIInsightRecommendationConfirmResponse:
        rows = self._repository.confirm_recommendation_drafts(
            draft_ids=draft_ids,
            confirmed_by_id=confirmed_by_id,
        )
        tasks = [
            AIInsightConfirmedTask(
                draftId=str(row["draft_id"]),
                taskId=str(row["task_id"]),
                title=str(row["title"]),
                status=str(row["status"]),
                priority=str(row["priority"]),
                createdAt=row["created_at"],
            )
            for row in rows
        ]
        return AIInsightRecommendationConfirmResponse(
            confirmedAtUtc=datetime.now(UTC),
            confirmedCount=len(tasks),
            tasks=tasks,
        )

    def refresh_sensor_snapshot(self, *, provider: str | None = None) -> dict[str, int]:
        return self._repository.refresh_sensor_24h_samples(provider=self._resolve_provider(provider))

    def _generate_summary(
        self,
        *,
        hours: int,
        zone: str | None,
        provider: str,
        mode: str,
    ) -> AIInsightSummaryResponse:
        self._repository.refresh_sensor_24h_samples(provider=provider)

        now_utc = datetime.now(UTC)
        start_utc = now_utc - timedelta(hours=hours)
        latest_sample_at = self._repository.get_latest_sample_at(provider=provider, zone=zone)
        freshness_status, warning_message = self._resolve_freshness(latest_sample_at=latest_sample_at, now_utc=now_utc)

        if freshness_status == "STALE":
            executive = AIInsightExecutive(
                headline="数据新鲜度不足，暂不生成新结论。",
                riskLevel="HIGH",
                keyFindings=[
                    "最新 partner_api 采样超过 30 分钟未更新。",
                    "系统仅展示历史摘要缓存，不生成新的建议草稿。",
                ],
            )
            response = AIInsightSummaryResponse(
                meta=AIInsightSummaryMeta(
                    source=provider,
                    freshnessStatus=freshness_status,
                    pageRefreshedAt=now_utc,
                    latestSampleAtUtc=latest_sample_at,
                    latestSampleAtLocal=self._to_local_text(latest_sample_at),
                    engineProvider="fallback",
                    engineModel=None,
                    fallbackUsed=True,
                    warningMessage=warning_message,
                ),
                executive=executive,
                expert=[],
                visual=AIInsightVisual(),
                recommendationDrafts=self._list_pending_drafts(limit=20),
            )
            self._repository.create_summary_run(
                hours=hours,
                zone=zone,
                provider=provider,
                mode=mode,
                engine_provider="fallback",
                engine_model=None,
                fallback_used=True,
                freshness_status=freshness_status,
                latest_sample_at=latest_sample_at,
                payload=response.model_dump(mode="json"),
            )
            return response

        metric_rows = self._repository.fetch_metric_stats(
            start_utc=start_utc,
            end_utc=now_utc,
            zone=zone,
            provider=provider,
        )
        anomaly_rows = self._repository.fetch_metric_anomalies(
            start_utc=start_utc,
            end_utc=now_utc,
            zone=zone,
            provider=provider,
            temperature_low=DEFAULT_THRESHOLDS["temperature"][0],
            temperature_high=DEFAULT_THRESHOLDS["temperature"][1],
            humidity_low=DEFAULT_THRESHOLDS["humidity"][0],
            humidity_high=DEFAULT_THRESHOLDS["humidity"][1],
            ec_low=DEFAULT_THRESHOLDS["ec"][0],
            ec_high=DEFAULT_THRESHOLDS["ec"][1],
            ph_low=DEFAULT_THRESHOLDS["ph"][0],
            ph_high=DEFAULT_THRESHOLDS["ph"][1],
        )
        disease_rows = self._repository.fetch_disease_counts(start_utc=start_utc, end_utc=now_utc)
        zone_risk_rows = self._repository.fetch_zone_risks(start_utc=start_utc, end_utc=now_utc, provider=provider)
        trend_rows = self._repository.fetch_metric_trends(
            start_utc=start_utc,
            end_utc=now_utc,
            zone=zone,
            provider=provider,
        )

        metrics = self._build_metric_snapshots(metric_rows=metric_rows, anomaly_rows=anomaly_rows)
        data_evidence_pool = self._build_data_evidence_pool(metrics=metrics, disease_rows=disease_rows)
        knowledge_refs = self._select_knowledge_refs(metrics=metrics, disease_rows=disease_rows, limit=8)
        analysis = self._generate_analysis_with_fallback(
            metrics=metrics,
            disease_rows=disease_rows,
            knowledge_refs=knowledge_refs,
            hours=hours,
            zone=zone,
        )
        expert_items = self._build_expert_items(
            expert_raw=analysis.expert_items,
            data_evidence_pool=data_evidence_pool,
            knowledge_refs=knowledge_refs,
        )

        visual = AIInsightVisual(
            zoneRisks=[
                AIInsightZoneRiskItem(
                    zone=str(row.get("zone") or "未知分区"),
                    riskScore=round(min(100.0, float(row.get("anomaly_minutes") or 0.0) * 0.6 + float(row.get("anomalous_samples") or 0) * 0.4), 2),
                    anomalyMinutes=round(float(row.get("anomaly_minutes") or 0.0), 2),
                    anomalousSamples=int(row.get("anomalous_samples") or 0),
                )
                for row in zone_risk_rows
            ],
            trends=[
                AIInsightTrendPoint(
                    metric=str(row.get("metric") or "temperature"),
                    bucketStartUtc=row["bucket_start"],
                    bucketStartLocal=self._to_local_text(row["bucket_start"]),
                    avg=round(float(row.get("avg_value") or 0.0), 3),
                    min=round(float(row.get("min_value") or 0.0), 3),
                    max=round(float(row.get("max_value") or 0.0), 3),
                    count=int(row.get("sample_count") or 0),
                )
                for row in trend_rows
                if isinstance(row.get("bucket_start"), datetime)
            ],
            anomalyTimeline=[
                AIInsightAnomalyTimelineItem(
                    metric=item.metric, anomalyDurationMinutes=round(item.anomaly_minutes, 2), anomalousSamples=item.anomalous_samples
                )
                for item in metrics.values()
            ],
        )

        response = AIInsightSummaryResponse(
            meta=AIInsightSummaryMeta(
                source=provider,
                freshnessStatus=freshness_status,
                pageRefreshedAt=now_utc,
                latestSampleAtUtc=latest_sample_at,
                latestSampleAtLocal=self._to_local_text(latest_sample_at),
                engineProvider=analysis.llm_provider,
                engineModel=analysis.llm_model,
                fallbackUsed=analysis.fallback_used,
                warningMessage=warning_message,
            ),
            executive=analysis.executive,
            expert=expert_items,
            visual=visual,
            recommendationDrafts=self._list_pending_drafts(limit=20),
        )
        self._repository.create_summary_run(
            hours=hours,
            zone=zone,
            provider=provider,
            mode=mode,
            engine_provider=analysis.llm_provider,
            engine_model=analysis.llm_model,
            fallback_used=analysis.fallback_used,
            freshness_status=freshness_status,
            latest_sample_at=latest_sample_at,
            payload=response.model_dump(mode="json"),
        )
        return response

    def _generate_analysis_with_fallback(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
        knowledge_refs: list[dict[str, Any]],
        hours: int,
        zone: str | None,
    ) -> _AnalysisResult:
        if self._settings.deepseek_api_key.strip():
            try:
                return self._generate_with_deepseek(
                    metrics=metrics,
                    disease_rows=disease_rows,
                    knowledge_refs=knowledge_refs,
                    hours=hours,
                    zone=zone,
                )
            except Exception:  # noqa: BLE001
                pass
        if self._settings.local_llm_enabled:
            try:
                return self._generate_with_local_llm(
                    metrics=metrics,
                    disease_rows=disease_rows,
                    knowledge_refs=knowledge_refs,
                    hours=hours,
                    zone=zone,
                )
            except Exception:  # noqa: BLE001
                pass
        return self._generate_with_fallback(metrics=metrics, disease_rows=disease_rows, hours=hours, zone=zone)

    def _generate_with_deepseek(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
        knowledge_refs: list[dict[str, Any]],
        hours: int,
        zone: str | None,
    ) -> _AnalysisResult:
        base_url = self._settings.deepseek_base_url.rstrip("/")
        prompt = self._build_deepseek_prompt(
            metrics=metrics,
            disease_rows=disease_rows,
            knowledge_refs=knowledge_refs,
            hours=hours,
            zone=zone,
        )
        payload = {
            "model": self._settings.deepseek_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是番茄连栋玻璃温室运营专家。"
                        "请严格返回 JSON。"
                        "字段: executive{headline,riskLevel,keyFindings[]},"
                        "expert[{title,problem,cause,action,priority}],"
                        "recommendations[{title,description,reason,priority,suggestedRole,dueHours}]。"
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }
        with httpx.Client(timeout=self._settings.deepseek_timeout_seconds, trust_env=False) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.deepseek_api_key.strip()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()

        choices = response_payload.get("choices") or []
        if not choices:
            raise ValueError("DeepSeek response missing choices.")
        content = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        parsed = self._parse_json_content(content)

        executive_raw = parsed.get("executive") if isinstance(parsed.get("executive"), dict) else {}
        risk_level = str(executive_raw.get("riskLevel") or "").upper()
        if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
            risk_level = "MEDIUM"
        executive = AIInsightExecutive(
            headline=str(executive_raw.get("headline") or "智能解析已生成。")[:200],
            riskLevel=risk_level,
            keyFindings=[
                str(item).strip()
                for item in (executive_raw.get("keyFindings") or [])
                if str(item).strip()
            ][:6],
        )

        expert_items: list[dict[str, Any]] = []
        for item in parsed.get("expert") or []:
            if not isinstance(item, dict):
                continue
            priority = str(item.get("priority") or "").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"
            expert_items.append(
                {
                    "title": str(item.get("title") or "").strip()[:120],
                    "problem": str(item.get("problem") or "").strip()[:300],
                    "cause": str(item.get("cause") or "").strip()[:300],
                    "action": str(item.get("action") or "").strip()[:600],
                    "priority": priority,
                }
            )

        recommendations: list[dict[str, Any]] = []
        for item in parsed.get("recommendations") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not title or not description or not reason:
                continue
            priority = str(item.get("priority") or "").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"
            role = str(item.get("suggestedRole") or "").upper()
            if role not in {"SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"}:
                role = "WORKER"
            due_hours = self._normalize_due_hours(item.get("dueHours"))
            recommendations.append(
                {
                    "title": title[:120],
                    "description": description[:600],
                    "reason": reason[:300],
                    "priority": priority,
                    "suggested_role": role,
                    "due_hours": due_hours,
                }
            )

        if not expert_items:
            raise ValueError("DeepSeek expert output is empty.")
        if not recommendations:
            recommendations = self._build_recommendations_from_expert(expert_items=expert_items, max_items=3)

        return _AnalysisResult(
            executive=executive,
            expert_items=expert_items,
            recommendations=recommendations,
            llm_provider="deepseek",
            llm_model=str(response_payload.get("model") or self._settings.deepseek_model),
            fallback_used=False,
        )

    def _generate_with_fallback(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
        hours: int,
        zone: str | None,
    ) -> _AnalysisResult:
        scope_text = f"分区 {zone}" if zone else "全场"
        high_count = sum(1 for item in metrics.values() if item.anomaly_minutes >= 60)
        warning_count = sum(1 for item in metrics.values() if 20 <= item.anomaly_minutes < 60)
        disease_total = sum(int(row.get("total_count") or 0) for row in disease_rows)

        if high_count > 0:
            risk = "HIGH"
            headline = f"{scope_text}存在高风险指标波动，建议优先处理。"
        elif warning_count > 0 or disease_total > 0:
            risk = "MEDIUM"
            headline = f"{scope_text}出现中等风险波动，建议加强巡检。"
        else:
            risk = "LOW"
            headline = f"{scope_text}整体运行平稳，建议持续监测。"

        key_findings = []
        for metric in METRIC_ORDER:
            item = metrics[metric]
            if item.sample_count <= 0 or item.avg is None:
                key_findings.append(f"{METRIC_LABELS[metric]}暂无有效样本。")
                continue
            key_findings.append(
                f"{METRIC_LABELS[metric]}均值 {item.avg:.2f}{METRIC_UNITS[metric]}，异常 {item.anomaly_minutes:.1f} 分钟。"
            )
        if disease_total > 0:
            top = str((disease_rows[0] if disease_rows else {}).get("disease_type") or "UNKNOWN")
            key_findings.append(f"病害识别事件 {disease_total} 次，主要类型 {top}。")

        expert_items: list[dict[str, Any]] = []
        for metric in METRIC_ORDER:
            item = metrics[metric]
            if item.sample_count <= 0 or item.avg is None:
                continue
            if item.anomaly_minutes < 20:
                continue
            label = METRIC_LABELS[metric]
            priority = "HIGH" if item.anomaly_minutes >= 60 else "MEDIUM"
            expert_items.append(
                {
                    "title": f"{label}波动处置与控制参数复核",
                    "problem": f"近{hours}小时 {label}异常累计 {item.anomaly_minutes:.1f} 分钟，波动较明显。",
                    "cause": f"可能存在执行器响应滞后、策略阈值偏紧或局部分区工况波动。",
                    "action": f"建议复核{label}控制阈值、检查关键传感器与执行器，并在下一班次复测。",
                    "priority": priority,
                }
            )
        if disease_total > 0:
            top = str((disease_rows[0] if disease_rows else {}).get("disease_type") or "UNKNOWN")
            expert_items.append(
                {
                    "title": "病害高风险点位复检",
                    "problem": f"近{hours}小时病害识别事件 {disease_total} 次，存在扩散风险。",
                    "cause": f"当前高频病害类型为 {top}，可能与夜间湿度控制与通风策略有关。",
                    "action": "建议对高风险分区进行复检，执行隔离与精准植保，回填处理结果。",
                    "priority": "HIGH",
                }
            )
        if not expert_items:
            expert_items.append(
                {
                    "title": "运行稳定性复核",
                    "problem": "当前未观察到明显异常，但需防止隐性波动累积。",
                    "cause": "班次交接、灌溉切换和夜间环境回落阶段容易出现短时偏移。",
                    "action": "建议保持 24h 连续巡检，重点关注夜间湿度回落与灌溉执行稳定性。",
                    "priority": "LOW",
                }
            )

        recommendations = self._build_recommendations_from_expert(expert_items=expert_items, max_items=3)
        return _AnalysisResult(
            executive=AIInsightExecutive(
                headline=headline,
                riskLevel=risk,
                keyFindings=key_findings[:6],
            ),
            expert_items=expert_items,
            recommendations=recommendations,
            llm_provider="fallback",
            llm_model=None,
            fallback_used=True,
        )

    def _generate_recommendation_content(
        self,
        *,
        summary: AIInsightSummaryResponse,
        knowledge_refs: list[dict[str, Any]],
        instruction: str | None,
        max_items: int,
    ) -> _AnalysisResult:
        if self._settings.deepseek_api_key.strip():
            try:
                return self._generate_recommendations_with_deepseek(
                    summary=summary,
                    knowledge_refs=knowledge_refs,
                    instruction=instruction,
                    max_items=max_items,
                )
            except Exception:  # noqa: BLE001
                pass
        if self._settings.local_llm_enabled:
            try:
                return self._generate_recommendations_with_local_llm(
                    summary=summary,
                    knowledge_refs=knowledge_refs,
                    instruction=instruction,
                    max_items=max_items,
                )
            except Exception:  # noqa: BLE001
                pass

        expert_items = [
            {
                "title": item.title,
                "problem": item.problem,
                "cause": item.cause,
                "action": item.action,
                "priority": item.priority,
            }
            for item in summary.expert
        ]
        recommendations = self._build_recommendations_from_expert(expert_items=expert_items, max_items=max_items)
        if instruction and instruction.strip() and len(recommendations) < max_items:
            recommendations.append(
                {
                    "title": "专项关注执行",
                    "description": f"针对“{instruction.strip()}”建立专项跟踪并在 24 小时内回填执行结果。",
                    "reason": "已接收补充关注方向，需要在任务流中形成可追踪闭环。",
                    "priority": "MEDIUM",
                    "suggested_role": "EXPERT",
                    "due_hours": 24,
                }
            )

        enriched = []
        for item in recommendations[:max_items]:
            enriched.append(
                {
                    **item,
                    "knowledge_refs": [str(ref.get("id")) for ref in knowledge_refs[:4] if ref.get("id")],
                    "data_evidence": [e.model_dump(mode="json") for e in summary.expert[0].dataEvidence[:3]]
                    if summary.expert
                    else [],
                    "knowledge_evidence": [k.model_dump(mode="json") for k in summary.expert[0].knowledgeEvidence[:3]]
                    if summary.expert
                    else [],
                    "metadata": {"instruction": instruction.strip() if instruction else None},
                }
            )

        return _AnalysisResult(
            executive=summary.executive,
            expert_items=expert_items,
            recommendations=enriched,
            llm_provider="fallback",
            llm_model=None,
            fallback_used=True,
        )

    def _generate_recommendations_with_deepseek(
        self,
        *,
        summary: AIInsightSummaryResponse,
        knowledge_refs: list[dict[str, Any]],
        instruction: str | None,
        max_items: int,
    ) -> _AnalysisResult:
        base_url = self._settings.deepseek_base_url.rstrip("/")
        prompt = self._build_deepseek_recommendation_prompt(
            summary=summary,
            knowledge_refs=knowledge_refs,
            instruction=instruction,
            max_items=max_items,
        )
        payload = {
            "model": self._settings.deepseek_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是番茄温室运营专家。严格返回 JSON。"
                        "字段 recommendations 数组，每项包含 title,description,reason,priority,suggestedRole,dueHours。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        with httpx.Client(timeout=self._settings.deepseek_timeout_seconds, trust_env=False) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.deepseek_api_key.strip()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()

        choices = response_payload.get("choices") or []
        if not choices:
            raise ValueError("DeepSeek recommendations missing choices.")
        content = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        parsed = self._parse_json_content(content)

        recommendations: list[dict[str, Any]] = []
        for item in parsed.get("recommendations") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not title or not description or not reason:
                continue
            priority = str(item.get("priority") or "").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"
            role = str(item.get("suggestedRole") or "").upper()
            if role not in {"SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"}:
                role = "WORKER"
            recommendations.append(
                {
                    "title": title[:120],
                    "description": description[:600],
                    "reason": reason[:300],
                    "priority": priority,
                    "suggested_role": role,
                    "due_hours": self._normalize_due_hours(item.get("dueHours")),
                    "knowledge_refs": [str(ref.get("id")) for ref in knowledge_refs[:6] if ref.get("id")],
                    "data_evidence": [e.model_dump(mode="json") for e in summary.expert[0].dataEvidence[:3]]
                    if summary.expert
                    else [],
                    "knowledge_evidence": [k.model_dump(mode="json") for k in summary.expert[0].knowledgeEvidence[:3]]
                    if summary.expert
                    else [],
                    "metadata": {"instruction": instruction.strip() if instruction else None},
                }
            )
            if len(recommendations) >= max_items:
                break
        if not recommendations:
            raise ValueError("DeepSeek recommendations empty.")

        return _AnalysisResult(
            executive=summary.executive,
            expert_items=[],
            recommendations=recommendations,
            llm_provider="deepseek",
            llm_model=str(response_payload.get("model") or self._settings.deepseek_model),
            fallback_used=False,
        )

    def _generate_with_local_llm(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
        knowledge_refs: list[dict[str, Any]],
        hours: int,
        zone: str | None,
    ) -> _AnalysisResult:
        base_url = self._settings.local_llm_base_url.rstrip("/")
        prompt = self._build_deepseek_prompt(
            metrics=metrics,
            disease_rows=disease_rows,
            knowledge_refs=knowledge_refs,
            hours=hours,
            zone=zone,
        )
        payload = {
            "model": self._settings.local_llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是番茄连栋玻璃温室运营专家。"
                        "请严格返回 JSON。"
                        "字段: executive{headline,riskLevel,keyFindings[]},"
                        "expert[{title,problem,cause,action,priority}],"
                        "recommendations[{title,description,reason,priority,suggestedRole,dueHours}]。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        with httpx.Client(timeout=self._settings.local_llm_timeout_seconds, trust_env=False) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()

        choices = response_payload.get("choices") or []
        if not choices:
            raise ValueError("Local LLM response missing choices.")
        content = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        parsed = self._parse_json_content(content)

        executive_raw = parsed.get("executive") if isinstance(parsed.get("executive"), dict) else {}
        risk_level = str(executive_raw.get("riskLevel") or "").upper()
        if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
            risk_level = "MEDIUM"
        executive = AIInsightExecutive(
            headline=str(executive_raw.get("headline") or "智能解析已生成。")[:200],
            riskLevel=risk_level,
            keyFindings=[str(item).strip() for item in (executive_raw.get("keyFindings") or []) if str(item).strip()][:6],
        )

        expert_items: list[dict[str, Any]] = []
        for item in parsed.get("expert") or []:
            if not isinstance(item, dict):
                continue
            priority = str(item.get("priority") or "").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"
            expert_items.append(
                {
                    "title": str(item.get("title") or "").strip()[:120],
                    "problem": str(item.get("problem") or "").strip()[:300],
                    "cause": str(item.get("cause") or "").strip()[:300],
                    "action": str(item.get("action") or "").strip()[:600],
                    "priority": priority,
                }
            )

        recommendations = self._build_recommendations_from_expert(
            expert_items=expert_items,
            max_items=3,
        )
        if not expert_items:
            raise ValueError("Local LLM expert output is empty.")
        return _AnalysisResult(
            executive=executive,
            expert_items=expert_items,
            recommendations=recommendations,
            llm_provider="local_llm",
            llm_model=str(response_payload.get("model") or self._settings.local_llm_model),
            fallback_used=False,
        )

    def _generate_recommendations_with_local_llm(
        self,
        *,
        summary: AIInsightSummaryResponse,
        knowledge_refs: list[dict[str, Any]],
        instruction: str | None,
        max_items: int,
    ) -> _AnalysisResult:
        base_url = self._settings.local_llm_base_url.rstrip("/")
        prompt = self._build_deepseek_recommendation_prompt(
            summary=summary,
            knowledge_refs=knowledge_refs,
            instruction=instruction,
            max_items=max_items,
        )
        payload = {
            "model": self._settings.local_llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是番茄温室运营专家。严格返回 JSON。"
                        "字段 recommendations 数组，每项包含 title,description,reason,priority,suggestedRole,dueHours。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        with httpx.Client(timeout=self._settings.local_llm_timeout_seconds, trust_env=False) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()

        choices = response_payload.get("choices") or []
        if not choices:
            raise ValueError("Local LLM recommendations missing choices.")
        content = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
        parsed = self._parse_json_content(content)
        recommendations: list[dict[str, Any]] = []
        for item in parsed.get("recommendations") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not title or not description or not reason:
                continue
            priority = str(item.get("priority") or "").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"
            role = str(item.get("suggestedRole") or "").upper()
            if role not in {"SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"}:
                role = "WORKER"
            recommendations.append(
                {
                    "title": title[:120],
                    "description": description[:600],
                    "reason": reason[:300],
                    "priority": priority,
                    "suggested_role": role,
                    "due_hours": self._normalize_due_hours(item.get("dueHours")),
                    "knowledge_refs": [str(ref.get("id")) for ref in knowledge_refs[:6] if ref.get("id")],
                    "data_evidence": [e.model_dump(mode="json") for e in summary.expert[0].dataEvidence[:3]]
                    if summary.expert
                    else [],
                    "knowledge_evidence": [k.model_dump(mode="json") for k in summary.expert[0].knowledgeEvidence[:3]]
                    if summary.expert
                    else [],
                    "metadata": {"instruction": instruction.strip() if instruction else None},
                }
            )
            if len(recommendations) >= max_items:
                break
        if not recommendations:
            raise ValueError("Local LLM recommendations empty.")

        return _AnalysisResult(
            executive=summary.executive,
            expert_items=[],
            recommendations=recommendations,
            llm_provider="local_llm",
            llm_model=str(response_payload.get("model") or self._settings.local_llm_model),
            fallback_used=False,
        )

    def _build_deepseek_prompt(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
        knowledge_refs: list[dict[str, Any]],
        hours: int,
        zone: str | None,
    ) -> str:
        metric_lines = []
        for metric in METRIC_ORDER:
            item = metrics[metric]
            metric_lines.append(
                f"{metric}: avg={item.avg}, min={item.min}, max={item.max}, latest={item.latest}, "
                f"sampleCount={item.sample_count}, anomalyMinutes={item.anomaly_minutes}"
            )
        disease_lines = [f"{row.get('disease_type')}:{row.get('total_count')}" for row in disease_rows[:6]]
        knowledge_lines = [
            f"- {item.get('title')} | {item.get('summary')} | 关键词:{','.join(item.get('keywords') or [])}"
            for item in knowledge_refs[:8]
        ]
        return (
            f"时间窗口: 最近{hours}小时\n"
            f"范围: {zone or '全场'}\n"
            f"指标: {' | '.join(metric_lines)}\n"
            f"病害: {', '.join(disease_lines) if disease_lines else '无'}\n"
            f"知识参考:\n{chr(10).join(knowledge_lines) if knowledge_lines else '- 无'}\n"
            "请给出管理层摘要和专家解析，并附可执行建议。"
        )

    def _build_deepseek_recommendation_prompt(
        self,
        *,
        summary: AIInsightSummaryResponse,
        knowledge_refs: list[dict[str, Any]],
        instruction: str | None,
        max_items: int,
    ) -> str:
        expert_lines = [f"- {item.title}: {item.problem} -> {item.action}" for item in summary.expert[:6]]
        knowledge_lines = [f"- {item.get('title')} | {item.get('summary')}" for item in knowledge_refs[:8]]
        return (
            f"页面执行摘要: {summary.executive.headline}\n"
            f"风险等级: {summary.executive.riskLevel}\n"
            f"专家结论:\n{chr(10).join(expert_lines) if expert_lines else '- 无'}\n"
            f"知识参考:\n{chr(10).join(knowledge_lines) if knowledge_lines else '- 无'}\n"
            f"补充指令: {instruction.strip() if instruction and instruction.strip() else '无'}\n"
            f"请输出不超过 {max_items} 条建议。"
        )

    def _build_recommendations_from_expert(self, *, expert_items: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in expert_items[:max_items]:
            priority = str(item.get("priority") or "MEDIUM").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"
            output.append(
                {
                    "title": str(item.get("title") or "执行建议")[:120],
                    "description": str(item.get("action") or "请执行分区复核并回填结果。")[:600],
                    "reason": str(item.get("cause") or "根据近24小时数据波动生成。")[:300],
                    "priority": priority,
                    "suggested_role": "EXPERT" if priority == "HIGH" else "WORKER",
                    "due_hours": 12 if priority == "HIGH" else 24,
                }
            )
        if not output:
            output.append(
                {
                    "title": "常规巡检与回填",
                    "description": "建议完成本班次温室巡检，重点复核夜间湿度回落与水肥执行记录。",
                    "reason": "当前暂无明确高风险事件，需保持持续监测和执行闭环。",
                    "priority": "LOW",
                    "suggested_role": "WORKER",
                    "due_hours": 24,
                }
            )
        return output[:max_items]

    def _build_metric_snapshots(
        self,
        *,
        metric_rows: list[dict[str, Any]],
        anomaly_rows: list[dict[str, Any]],
    ) -> dict[str, _MetricSnapshot]:
        metric_map = {str(row.get("metric")): row for row in metric_rows}
        anomaly_map = {str(row.get("metric")): row for row in anomaly_rows}
        output: dict[str, _MetricSnapshot] = {}
        for metric in METRIC_ORDER:
            metric_row = metric_map.get(metric) or {}
            anomaly_row = anomaly_map.get(metric) or {}
            output[metric] = _MetricSnapshot(
                metric=metric,
                avg=float(metric_row["avg_value"]) if metric_row.get("avg_value") is not None else None,
                min=float(metric_row["min_value"]) if metric_row.get("min_value") is not None else None,
                max=float(metric_row["max_value"]) if metric_row.get("max_value") is not None else None,
                latest=float(metric_row["latest_value"]) if metric_row.get("latest_value") is not None else None,
                sample_count=int(metric_row.get("sample_count") or 0),
                anomaly_minutes=round(float(anomaly_row.get("anomaly_seconds") or 0.0) / 60, 2),
                anomalous_samples=int(anomaly_row.get("anomalous_samples") or 0),
            )
        return output

    def _build_data_evidence_pool(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
    ) -> list[AIInsightDataEvidence]:
        evidences: list[AIInsightDataEvidence] = []
        for metric in METRIC_ORDER:
            item = metrics[metric]
            if item.avg is None:
                continue
            evidences.append(
                AIInsightDataEvidence(
                    label=f"{METRIC_LABELS[metric]}均值",
                    value=f"{item.avg:.2f}{METRIC_UNITS[metric]}（异常 {item.anomaly_minutes:.1f} 分钟）",
                )
            )
        disease_total = sum(int(row.get("total_count") or 0) for row in disease_rows)
        evidences.append(
            AIInsightDataEvidence(
                label="病害识别事件",
                value=f"{disease_total} 次",
            )
        )
        return evidences[:12]

    def _build_expert_items(
        self,
        *,
        expert_raw: list[dict[str, Any]],
        data_evidence_pool: list[AIInsightDataEvidence],
        knowledge_refs: list[dict[str, Any]],
    ) -> list[AIInsightExpertItem]:
        fallback_data = data_evidence_pool[:2] if data_evidence_pool else [AIInsightDataEvidence(label="数据证据", value="无可用明细")]
        fallback_knowledge = self._knowledge_rows_to_evidence(knowledge_refs[:2])
        if not fallback_knowledge:
            fallback_knowledge = [AIInsightKnowledgeEvidence(id="kb-fallback", title="知识依据缺失", summary="当前未匹配到知识条目。", sourceUrl=None)]

        items: list[AIInsightExpertItem] = []
        for row in expert_raw[:6]:
            title = str(row.get("title") or "").strip() or "专业解析结论"
            problem = str(row.get("problem") or "").strip() or "指标存在波动，需要进一步排查。"
            cause = str(row.get("cause") or "").strip() or "可能与控制参数或执行器响应有关。"
            action = str(row.get("action") or "").strip() or "建议进行分区复核并执行闭环处理。"
            priority = str(row.get("priority") or "").upper()
            if priority not in {"LOW", "MEDIUM", "HIGH"}:
                priority = "MEDIUM"

            items.append(
                AIInsightExpertItem(
                    title=title,
                    problem=problem,
                    cause=cause,
                    action=action,
                    priority=priority,
                    dataEvidence=fallback_data,
                    knowledgeEvidence=fallback_knowledge,
                )
            )
        return items

    def _select_knowledge_refs(
        self,
        *,
        metrics: dict[str, _MetricSnapshot],
        disease_rows: list[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        tokens: list[str] = ["番茄", "温室", "连栋", "水肥", "植保", "园艺", "病害", "湿度", "EC", "pH"]
        for metric in METRIC_ORDER:
            item = metrics[metric]
            tokens.append(metric)
            if item.anomaly_minutes > 0:
                tokens.append("异常")
        for row in disease_rows:
            tokens.append(str(row.get("disease_type") or ""))
        return self._match_knowledge_refs(tokens=tokens, limit=limit)

    def _select_knowledge_refs_from_summary(
        self,
        *,
        summary: AIInsightSummaryResponse,
        limit: int,
    ) -> list[dict[str, Any]]:
        tokens: list[str] = []
        tokens.extend(summary.executive.keyFindings)
        for item in summary.expert:
            tokens.extend([item.title, item.problem, item.cause, item.action])
        return self._match_knowledge_refs(tokens=tokens, limit=limit)

    def _match_knowledge_refs(self, *, tokens: list[str], limit: int) -> list[dict[str, Any]]:
        document = self._knowledge_repository.get_document()
        items = [item for item in document.get("items", []) if isinstance(item, dict)]
        normalized_tokens = [token.lower() for token in self._extract_tokens(" ".join(tokens))]
        if not normalized_tokens:
            return items[:limit]

        scored: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            haystack = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("whyImportant") or ""),
                    " ".join(str(keyword) for keyword in item.get("keywords", [])),
                ]
            ).lower()
            score = 0
            for token in normalized_tokens[:40]:
                if token and token in haystack:
                    score += 1
            if score > 0:
                scored.append((score, item))
        scored.sort(
            key=lambda pair: (pair[0], str(pair[1].get("updatedAt") or "")),
            reverse=True,
        )
        return [item for _, item in scored[:limit]] if scored else items[:limit]

    def _knowledge_rows_to_evidence(self, rows: list[dict[str, Any]]) -> list[AIInsightKnowledgeEvidence]:
        evidences: list[AIInsightKnowledgeEvidence] = []
        for row in rows:
            evidences.append(
                AIInsightKnowledgeEvidence(
                    id=str(row.get("id") or ""),
                    title=str(row.get("title") or "知识条目"),
                    summary=str(row.get("summary") or "")[:180],
                    sourceUrl=str((row.get("source") or {}).get("url") or "") or None,
                )
            )
        return evidences

    def _list_pending_drafts(self, *, limit: int) -> list[AIInsightDraftItem]:
        rows = self._repository.list_pending_recommendation_drafts(limit=limit)
        return [self._row_to_draft_item(row) for row in rows]

    def _row_to_draft_item(self, row: dict[str, Any]) -> AIInsightDraftItem:
        return AIInsightDraftItem(
            draftId=str(row.get("draft_id") or ""),
            title=str(row.get("title") or ""),
            description=str(row.get("description") or ""),
            reason=str(row.get("reason") or ""),
            priority=str(row.get("priority") or "MEDIUM"),
            suggestedRole=str(row.get("suggested_role") or "WORKER"),
            dueHours=int(row.get("due_hours") or 24),
            status=str(row.get("status") or "PENDING"),
            llmProvider=str(row.get("llm_provider") or "fallback"),
            llmModel=str(row.get("llm_model") or "") or None,
            fallbackUsed=bool(row.get("fallback_used")),
            knowledgeRefs=[str(item) for item in (row.get("knowledge_refs") or [])],
            dataEvidence=[
                AIInsightDataEvidence(
                    label=str(item.get("label") or "数据证据"),
                    value=str(item.get("value") or ""),
                )
                for item in (row.get("data_evidence") or [])
                if isinstance(item, dict)
            ],
            knowledgeEvidence=[
                AIInsightKnowledgeEvidence(
                    id=str(item.get("id") or ""),
                    title=str(item.get("title") or "知识条目"),
                    summary=str(item.get("summary") or ""),
                    sourceUrl=str(item.get("sourceUrl") or "") or None,
                )
                for item in (row.get("knowledge_evidence") or [])
                if isinstance(item, dict)
            ],
            createdAt=row["created_at"],
            confirmedAt=row.get("confirmed_at"),
            taskId=str(row.get("task_id") or "") or None,
        )

    def _resolve_provider(self, provider: str | None) -> str:
        # T13.2: strict real source only.
        return "partner_api"

    def _normalize_zone(self, zone: str | None) -> str | None:
        cleaned = str(zone or "").strip()
        if not cleaned or cleaned.lower() == "all":
            return None
        return cleaned

    def _resolve_freshness(self, *, latest_sample_at: datetime | None, now_utc: datetime) -> tuple[str, str | None]:
        if latest_sample_at is None:
            return "STALE", "当前时间范围内没有可用的 partner_api 采样数据。"
        lag = now_utc - latest_sample_at.astimezone(UTC)
        lag_minutes = lag.total_seconds() / 60
        if lag_minutes > 30:
            return "STALE", f"最新采样距今 {lag_minutes:.1f} 分钟，超过 30 分钟门禁。"
        if lag_minutes > 10:
            return "WARNING", f"最新采样距今 {lag_minutes:.1f} 分钟，建议关注数据链路。"
        return "FRESH", None

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response root must be an object.")
        return parsed

    def _extract_tokens(self, text: str) -> list[str]:
        return [item.lower() for item in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text or "")]

    def _normalize_due_hours(self, value: Any) -> int:
        try:
            due_hours = int(value)
        except Exception:  # noqa: BLE001
            return 24
        return max(1, min(due_hours, 168))

    def _to_local_text(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(self._display_timezone).strftime("%Y-%m-%d %H:%M:%S")
