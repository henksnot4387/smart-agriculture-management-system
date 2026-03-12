from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from app.ai.copilot.ai_insights_service import AIInsightsService
from app.core.config import settings
from app.integrations.hoogendoorn.dependencies import get_hoogendoorn_service
from app.repositories.ai_insights import AIInsightsRepository
from app.repositories.knowledge import LocalKnowledgeRepository
from app.repositories.settings import SettingsRepository
from app.repositories.task import TaskRepository
from app.repositories.vision import VisionTaskRepository
from app.scheduler.celery_app import celery_app
from app.scheduler.repository import SchedulerRepository
from app.scheduler.registry import JOB_DEFINITION_MAP
from app.services.knowledge_harvester import KnowledgeHarvester
from app.services.settings import SettingsService


def _run_job(job_id: str, trigger: str, runner) -> dict:
    repository = SchedulerRepository(settings)

    started = time.monotonic()
    run_id = repository.create_run(job_id=job_id, trigger=trigger)

    if repository.is_job_paused(job_id=job_id):
        repository.finish_run(
            run_id=run_id,
            status="SKIPPED",
            message="Job is paused.",
            error=None,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return {"job_id": job_id, "status": "SKIPPED", "message": "Job is paused."}

    try:
        message, payload = runner(repository)
        repository.finish_run(
            run_id=run_id,
            status="SUCCESS",
            message=message,
            error=None,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "message": message,
            "payload": payload,
            "finished_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        repository.finish_run(
            run_id=run_id,
            status="FAILED",
            message="Execution failed.",
            error=str(exc),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        raise


def _run_hoogendoorn_sync(repository: SchedulerRepository) -> tuple[str, dict]:
    service = get_hoogendoorn_service()
    result = asyncio.run(service.sync())
    rows_written = int(result.get("rows_written", 0))
    message = f"Hoogendoorn sync done: {rows_written} row(s) written."
    return message, result


def _run_knowledge_harvest(repository: SchedulerRepository) -> tuple[str, dict]:
    harvester = KnowledgeHarvester(settings=settings)
    result = harvester.harvest()
    message = (
        f"Knowledge harvest: {result['succeeded']} succeeded / {result['attempted']} attempted "
        f"(rate={result['success_rate']:.1f}%)."
    )
    return message, result


def _run_summary_precompute(repository: SchedulerRepository) -> tuple[str, dict]:
    ai_service = AIInsightsService(
        settings=settings,
        repository=AIInsightsRepository(settings),
        knowledge_repository=LocalKnowledgeRepository(),
    )
    summary = ai_service.get_summary(hours=24, zone=None, mode="refresh", provider="partner_api")
    payload = summary.model_dump(mode="json")

    repository.upsert_summary_cache(
        hours=24,
        zone="",
        provider="partner_api",
        payload=payload,
    )
    message = "AI 智能解析 24h 预计算完成。"
    return message, {"hours": 24, "provider": "partner_api", "freshness": summary.meta.freshnessStatus}


def _run_ai_insights_snapshot_refresh(repository: SchedulerRepository) -> tuple[str, dict]:
    ai_service = AIInsightsService(
        settings=settings,
        repository=AIInsightsRepository(settings),
        knowledge_repository=LocalKnowledgeRepository(),
    )
    result = ai_service.refresh_sensor_snapshot(provider="partner_api")
    message = (
        "AI 智能解析 24h 快照刷新完成："
        f"upserted={result.get('upserted', 0)}, purged={result.get('purged', 0)}"
    )
    return message, result


def _run_vision_timeout_cleanup(repository: SchedulerRepository) -> tuple[str, dict]:
    vision_repository = VisionTaskRepository(settings)
    affected = vision_repository.mark_processing_timeouts(
        timeout_minutes=settings.vision_processing_timeout_minutes,
        reason="Task timed out in PROCESSING state by scheduler.",
    )
    message = f"Vision timeout cleanup affected {affected} task(s)."
    return message, {"affected": affected}


def _run_settings_auto_task_dispatch(repository: SchedulerRepository) -> tuple[str, dict]:
    settings_service = SettingsService(
        repository=SettingsRepository(settings),
        task_repository=TaskRepository(settings),
    )
    fallback_actor = TaskRepository(settings).get_first_management_user_id()
    if not fallback_actor:
        return "No management user available, skipped settings auto task dispatch.", {"triggered": 0}
    results = settings_service.trigger_due_profiles(actor_user_id=fallback_actor)
    triggered = [item for item in results if item.triggered]
    message = f"Settings auto dispatch: {len(triggered)} task(s) created."
    return message, {"triggered": len(triggered), "profiles": [item.model_dump(mode='json') for item in results]}


@celery_app.task(name=JOB_DEFINITION_MAP["hoogendoorn_sync"].task_name)
def task_hoogendoorn_sync(trigger: str = "beat") -> dict:
    return _run_job("hoogendoorn_sync", trigger, _run_hoogendoorn_sync)


@celery_app.task(name=JOB_DEFINITION_MAP["knowledge_harvest"].task_name)
def task_knowledge_harvest(trigger: str = "beat") -> dict:
    return _run_job("knowledge_harvest", trigger, _run_knowledge_harvest)


@celery_app.task(name=JOB_DEFINITION_MAP["ai_insights_snapshot_refresh"].task_name)
def task_ai_insights_snapshot_refresh(trigger: str = "beat") -> dict:
    return _run_job("ai_insights_snapshot_refresh", trigger, _run_ai_insights_snapshot_refresh)


@celery_app.task(name=JOB_DEFINITION_MAP["copilot_summary_precompute"].task_name)
def task_copilot_summary_precompute(trigger: str = "beat") -> dict:
    return _run_job("copilot_summary_precompute", trigger, _run_summary_precompute)


@celery_app.task(name=JOB_DEFINITION_MAP["vision_timeout_cleanup"].task_name)
def task_vision_timeout_cleanup(trigger: str = "beat") -> dict:
    return _run_job("vision_timeout_cleanup", trigger, _run_vision_timeout_cleanup)


@celery_app.task(name=JOB_DEFINITION_MAP["settings_auto_task_dispatch"].task_name)
def task_settings_auto_task_dispatch(trigger: str = "beat") -> dict:
    return _run_job("settings_auto_task_dispatch", trigger, _run_settings_auto_task_dispatch)
