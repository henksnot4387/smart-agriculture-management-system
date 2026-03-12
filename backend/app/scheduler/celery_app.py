from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import beat_init, worker_ready

from app.core.config import settings
from app.scheduler.repository import SchedulerRepository
from app.scheduler.registry import JOB_DEFINITIONS


def _build_beat_schedule() -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for job in JOB_DEFINITIONS:
        if job.schedule_type == "interval" and job.interval_seconds:
            schedule = job.interval_seconds
        elif job.schedule_type == "cron" and job.cron_minute is not None and job.cron_hour is not None:
            schedule = crontab(minute=job.cron_minute, hour=job.cron_hour)
        else:
            continue

        entries[f"scheduler.{job.job_id}"] = {
            "task": job.task_name,
            "schedule": schedule,
            "kwargs": {"trigger": "beat"},
        }
    return entries


celery_app = Celery(
    "intellifarm_scheduler",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.scheduler.jobs"],
)

celery_app.conf.update(
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=False,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    beat_schedule=_build_beat_schedule(),
)


def bootstrap_scheduler_metadata() -> None:
    repository = SchedulerRepository(settings)
    repository.ensure_schema()
    repository.upsert_job_definitions(list(JOB_DEFINITIONS))


@worker_ready.connect
def on_worker_ready(**_: object) -> None:
    bootstrap_scheduler_metadata()


@beat_init.connect
def on_beat_init(**_: object) -> None:
    bootstrap_scheduler_metadata()
