from __future__ import annotations

from app.ai.copilot.types import RecommendationDraft, RecommendationGenerationResult
from app.schemas.copilot import CopilotSummaryResponse


class RuleBasedFallbackGenerator:
    def generate(
        self,
        *,
        summary: CopilotSummaryResponse,
        instruction: str | None,
        max_items: int,
    ) -> RecommendationGenerationResult:
        drafts: list[RecommendationDraft] = []

        metric_map = {
            "temperature": summary.metrics.temperature,
            "humidity": summary.metrics.humidity,
            "ec": summary.metrics.ec,
            "ph": summary.metrics.ph,
        }

        for metric, stats in metric_map.items():
            if len(drafts) >= max_items:
                break
            if stats.sampleCount <= 0 or stats.avg is None:
                continue
            if stats.anomalyDurationMinutes < 20:
                continue

            label = {"temperature": "温度", "humidity": "湿度", "ec": "EC", "ph": "pH"}[metric]
            drafts.append(
                RecommendationDraft(
                    title=f"{label}异常治理与参数复核",
                    description=(
                        f"近{summary.hours}小时 {label} 异常累计 {stats.anomalyDurationMinutes:.1f} 分钟，"
                        f"建议复核控制策略、传感器状态与执行器响应。"
                    ),
                    reason=(
                        f"{label}存在连续异常波动，当前阈值 {stats.lowThreshold}~{stats.highThreshold}，"
                        f"样本数 {stats.sampleCount}。"
                    ),
                    priority="HIGH" if stats.anomalyDurationMinutes >= 60 else "MEDIUM",
                    suggested_role="EXPERT",
                    due_hours=12 if stats.anomalyDurationMinutes >= 60 else 24,
                )
            )

        if summary.totalDiseaseEvents > 0 and len(drafts) < max_items:
            top = summary.diseaseCounts[0].diseaseType if summary.diseaseCounts else "病害"
            drafts.append(
                RecommendationDraft(
                    title="病害高风险分区复检与处置",
                    description=(
                        f"近{summary.hours}小时病害识别完成 {summary.totalDiseaseEvents} 次，"
                        f"建议对高频类型（如 {top}）开展复检并执行隔离/植保处置。"
                    ),
                    reason="病害识别事件数量上升，需快速闭环防止扩散。",
                    priority="HIGH",
                    suggested_role="WORKER",
                    due_hours=8,
                )
            )

        if len(drafts) < max_items:
            drafts.append(
                RecommendationDraft(
                    title="班次巡检与数据质量复核",
                    description=(
                        "建议在下一班次完成温室环境、灌溉执行器与关键传感器的巡检，"
                        "并确认异常时段的数据完整性。"
                    ),
                    reason="保障执行面稳定，避免异常由设备状态或数据质量问题放大。",
                    priority="MEDIUM",
                    suggested_role="WORKER",
                    due_hours=24,
                )
            )

        if instruction and instruction.strip() and len(drafts) < max_items:
            drafts.append(
                RecommendationDraft(
                    title="针对性专项建议执行",
                    description=f"结合操作指令“{instruction.strip()}”，建议建立专项跟踪并在 24 小时内回填执行结果。",
                    reason="用户提供了额外关注方向，需要在建议链路中保留并形成可追踪任务。",
                    priority="MEDIUM",
                    suggested_role="EXPERT",
                    due_hours=24,
                )
            )

        return RecommendationGenerationResult(
            provider="fallback",
            model=None,
            fallback_used=True,
            request_id=None,
            recommendations=drafts[:max_items],
        )
