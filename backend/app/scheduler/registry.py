from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerJobDefinition:
    job_id: str
    task_name: str
    name: str
    description: str
    schedule_type: str
    schedule_value: str
    interval_seconds: int | None = None
    cron_minute: str | None = None
    cron_hour: str | None = None


JOB_DEFINITIONS: tuple[SchedulerJobDefinition, ...] = (
    SchedulerJobDefinition(
        job_id="hoogendoorn_sync",
        task_name="scheduler.job.hoogendoorn_sync",
        name="Hoogendoorn 增量同步",
        description="拉取 Hoogendoorn 最新环境数据并补录到 sensor_data。",
        schedule_type="interval",
        schedule_value="每 5 分钟",
        interval_seconds=300,
    ),
    SchedulerJobDefinition(
        job_id="ai_insights_snapshot_refresh",
        task_name="scheduler.job.ai_insights_snapshot_refresh",
        name="AI智能解析24h快照刷新",
        description="刷新 partner_api 24h 样本快照（copilot_rt.sensor_24h_samples）。",
        schedule_type="interval",
        schedule_value="每 5 分钟",
        interval_seconds=300,
    ),
    SchedulerJobDefinition(
        job_id="knowledge_harvest",
        task_name="scheduler.job.knowledge_harvest",
        name="知识库采集刷新",
        description="按白名单 + API Key 来源刷新本地知识库。",
        schedule_type="cron",
        schedule_value="每天 03:30",
        cron_minute="30",
        cron_hour="3",
    ),
    SchedulerJobDefinition(
        job_id="copilot_summary_precompute",
        task_name="scheduler.job.copilot_summary_precompute",
        name="AI智能解析预计算",
        description="预计算近24小时 AI 智能解析并写入运行缓存。",
        schedule_type="interval",
        schedule_value="每 15 分钟",
        interval_seconds=900,
    ),
    SchedulerJobDefinition(
        job_id="vision_timeout_cleanup",
        task_name="scheduler.job.vision_timeout_cleanup",
        name="视觉任务超时清理",
        description="将长期 PROCESSING 的识别任务兜底标记为 FAILED。",
        schedule_type="interval",
        schedule_value="每 2 分钟",
        interval_seconds=120,
    ),
    SchedulerJobDefinition(
        job_id="settings_auto_task_dispatch",
        task_name="scheduler.job.settings_auto_task_dispatch",
        name="设置驱动任务自动触发",
        description="按园艺/植保/环控/水肥设置的启用策略自动创建任务。",
        schedule_type="interval",
        schedule_value="每 10 分钟",
        interval_seconds=600,
    ),
)

JOB_DEFINITION_MAP = {job.job_id: job for job in JOB_DEFINITIONS}
