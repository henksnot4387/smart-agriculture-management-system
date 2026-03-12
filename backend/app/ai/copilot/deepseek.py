from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.ai.copilot.types import RecommendationDraft, RecommendationGenerationResult
from app.core.config import Settings
from app.schemas.copilot import CopilotSummaryResponse


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self._api_key = settings.deepseek_api_key.strip()
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._model = settings.deepseek_model
        self._timeout = settings.deepseek_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        *,
        summary: CopilotSummaryResponse,
        instruction: str | None,
        knowledge_refs: list[dict[str, Any]],
        max_items: int,
    ) -> RecommendationGenerationResult:
        if not self.enabled:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured.")

        prompt = self._build_user_prompt(
            summary=summary,
            instruction=instruction,
            knowledge_refs=knowledge_refs,
            max_items=max_items,
        )
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是智慧农业管理系统的生产运营专家。"
                        "请返回严格 JSON，不要包含 markdown。"
                        "输出字段：recommendations（数组），每项必须包含 "
                        "title, description, reason, priority(LOW|MEDIUM|HIGH), "
                        "suggestedRole(SUPER_ADMIN|ADMIN|EXPERT|WORKER), dueHours(1-168)。"
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }

        with httpx.Client(timeout=self._timeout, trust_env=False) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
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
        raw_recommendations = parsed.get("recommendations")
        if not isinstance(raw_recommendations, list):
            raise ValueError("DeepSeek response missing recommendations array.")

        recommendations: list[RecommendationDraft] = []
        for item in raw_recommendations:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not title or not description or not reason:
                continue
            recommendations.append(
                RecommendationDraft(
                    title=title[:120],
                    description=description[:600],
                    reason=reason[:300],
                    priority=self._normalize_priority(item.get("priority")),
                    suggested_role=self._normalize_role(item.get("suggestedRole")),
                    due_hours=self._normalize_due_hours(item.get("dueHours")),
                )
            )
            if len(recommendations) >= max_items:
                break

        if not recommendations:
            raise ValueError("DeepSeek response did not yield valid recommendations.")

        request_id = (
            response.headers.get("x-request-id")
            or response_payload.get("id")
            or None
        )
        response_model = response_payload.get("model") or self._model
        return RecommendationGenerationResult(
            provider="deepseek",
            model=str(response_model) if response_model else self._model,
            fallback_used=False,
            request_id=str(request_id) if request_id else None,
            recommendations=recommendations,
        )

    def _build_user_prompt(
        self,
        *,
        summary: CopilotSummaryResponse,
        instruction: str | None,
        knowledge_refs: list[dict[str, Any]],
        max_items: int,
    ) -> str:
        metric_lines = []
        for metric in ("temperature", "humidity", "ec", "ph"):
            stats = getattr(summary.metrics, metric)
            metric_lines.append(
                f"{metric}: avg={stats.avg}, min={stats.min}, max={stats.max}, "
                f"sampleCount={stats.sampleCount}, anomalyMinutes={stats.anomalyDurationMinutes}"
            )
        disease_lines = [f"{item.diseaseType}:{item.count}" for item in summary.diseaseCounts[:6]]
        knowledge_lines = []
        for item in knowledge_refs[:8]:
            knowledge_lines.append(
                f"- {item.get('title')} | {item.get('summary')} | 建议: {'; '.join(item.get('actionablePoints') or [])}"
            )

        return (
            f"时间窗: 最近{summary.hours}小时\n"
            f"分区: {summary.zone or '全场'}\n"
            f"摘要: {summary.narrative}\n"
            f"指标: {' | '.join(metric_lines)}\n"
            f"病害: {', '.join(disease_lines) if disease_lines else '无'}\n"
            f"知识依据:\n{chr(10).join(knowledge_lines) if knowledge_lines else '- 无'}\n"
            f"补充指令: {instruction.strip() if instruction and instruction.strip() else '无'}\n"
            f"请生成不超过{max_items}条可执行建议。"
        )

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("DeepSeek response root must be a JSON object.")
        return parsed

    def _normalize_priority(self, value: Any) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in {"LOW", "MEDIUM", "HIGH"}:
            return normalized
        return "MEDIUM"

    def _normalize_role(self, value: Any) -> str:
        normalized = str(value or "").strip().upper()
        if normalized in {"SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"}:
            return normalized
        return "WORKER"

    def _normalize_due_hours(self, value: Any) -> int:
        try:
            due_hours = int(value)
        except Exception:  # noqa: BLE001
            return 24
        return max(1, min(due_hours, 168))
