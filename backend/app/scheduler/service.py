from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache

from redis import Redis

from app.core.config import settings
from app.scheduler.registry import JOB_DEFINITION_MAP, JOB_DEFINITIONS
from app.scheduler.repository import SchedulerRepository


class SchedulerService:
    def __init__(self, repository: SchedulerRepository):
        self._repository = repository

    def bootstrap(self) -> None:
        self._repository.ensure_schema()
        self._repository.upsert_job_definitions(list(JOB_DEFINITIONS))

    def list_jobs(self) -> list[dict]:
        now = datetime.now(UTC)
        jobs = self._repository.list_jobs()
        for job in jobs:
            job["next_run_at"] = self._compute_next_run(job, now)
        return jobs

    def list_runs(self, *, limit: int, job_id: str | None = None) -> list[dict]:
        return self._repository.list_runs(limit=limit, job_id=job_id)

    def pause_job(self, *, job_id: str) -> bool:
        return self._repository.set_paused(job_id=job_id, paused=True)

    def resume_job(self, *, job_id: str) -> bool:
        return self._repository.set_paused(job_id=job_id, paused=False)

    def dispatch_job(self, *, job_id: str) -> dict[str, str | None]:
        job = self._repository.get_job(job_id=job_id)
        if not job:
            raise KeyError(job_id)

        from app.scheduler.celery_app import celery_app

        async_result = celery_app.send_task(job["task_name"], kwargs={"trigger": "manual"})
        return {
            "job_id": str(job_id),
            "task_id": async_result.id,
            "dispatched_at": datetime.now(UTC),
        }

    def health(self) -> dict:
        broker_ok = False
        broker_error = None
        try:
            redis_client = Redis.from_url(settings.redis_url, decode_responses=False)
            broker_ok = bool(redis_client.ping())
            redis_client.close()
        except Exception as exc:  # noqa: BLE001
            broker_error = str(exc)

        db_health = self._repository.get_health()
        return {
            "broker_ok": broker_ok,
            "broker_error": broker_error,
            "total_jobs": db_health["total_jobs"],
            "paused_jobs": db_health["paused_jobs"],
            "latest_finished_at": db_health["latest_finished_at"],
            "timestamp": db_health["timestamp"],
        }

    def _compute_next_run(self, job: dict, now: datetime) -> datetime | None:
        if bool(job.get("is_paused")):
            return None

        schedule_type = str(job.get("schedule_type") or "")
        last_finished_at = job.get("last_run_finished_at")
        if schedule_type == "interval":
            seconds = int(job.get("interval_seconds") or 0)
            if seconds <= 0:
                return None
            if isinstance(last_finished_at, datetime):
                candidate = last_finished_at.astimezone(UTC) + timedelta(seconds=seconds)
                if candidate > now:
                    return candidate
            return now + timedelta(seconds=seconds)

        if schedule_type == "cron":
            minute = int(str(job.get("cron_minute") or "0"))
            hour = int(str(job.get("cron_hour") or "0"))
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        definition = JOB_DEFINITION_MAP.get(str(job.get("job_id") or ""))
        if definition and definition.interval_seconds:
            return now + timedelta(seconds=definition.interval_seconds)
        return None


@lru_cache
def get_scheduler_service() -> SchedulerService:
    service = SchedulerService(repository=SchedulerRepository(settings))
    service.bootstrap()
    return service
