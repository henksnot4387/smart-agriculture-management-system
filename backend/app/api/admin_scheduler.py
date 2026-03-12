from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth_context import ActorContext, require_roles
from app.core.security import require_api_token
from app.scheduler.service import SchedulerService, get_scheduler_service
from app.schemas.scheduler import (
    SchedulerDispatchResponse,
    SchedulerHealthResponse,
    SchedulerJob,
    SchedulerJobsResponse,
    SchedulerRun,
    SchedulerRunsResponse,
)

router = APIRouter(
    prefix="/api/admin/scheduler",
    tags=["admin-scheduler"],
    dependencies=[Depends(require_api_token)],
)

require_super_admin = require_roles({"SUPER_ADMIN"})


@router.get("/jobs", response_model=SchedulerJobsResponse)
def list_scheduler_jobs(
    _: ActorContext = Depends(require_super_admin),
    service: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerJobsResponse:
    jobs = [
        SchedulerJob(
            jobId=str(item["job_id"]),
            taskName=str(item["task_name"]),
            name=str(item["name"]),
            description=str(item["description"]),
            scheduleType=str(item["schedule_type"]),
            scheduleValue=str(item["schedule_value"]),
            isPaused=bool(item.get("is_paused", False)),
            lastStatus=item.get("last_status"),
            lastMessage=item.get("last_message"),
            lastError=item.get("last_error"),
            lastRunStartedAt=item.get("last_run_started_at"),
            lastRunFinishedAt=item.get("last_run_finished_at"),
            lastDurationMs=item.get("last_duration_ms"),
            nextRunAt=item.get("next_run_at"),
        )
        for item in service.list_jobs()
    ]
    return SchedulerJobsResponse(jobs=jobs)


@router.get("/runs", response_model=SchedulerRunsResponse)
def list_scheduler_runs(
    _: ActorContext = Depends(require_super_admin),
    limit: int = Query(default=100, ge=1, le=500),
    jobId: str | None = None,
    service: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerRunsResponse:
    runs = [
        SchedulerRun(
            id=int(item["id"]),
            jobId=str(item["job_id"]),
            trigger=str(item["trigger"]),
            status=str(item["status"]),
            message=item.get("message"),
            error=item.get("error"),
            startedAt=item["started_at"],
            finishedAt=item.get("finished_at"),
            durationMs=item.get("duration_ms"),
        )
        for item in service.list_runs(limit=limit, job_id=jobId)
    ]
    return SchedulerRunsResponse(runs=runs)


@router.post("/jobs/{job_id}/run", response_model=SchedulerDispatchResponse)
def run_scheduler_job_now(
    job_id: str,
    _: ActorContext = Depends(require_super_admin),
    service: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerDispatchResponse:
    try:
        payload = service.dispatch_job(job_id=job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduler job not found.") from exc

    return SchedulerDispatchResponse(
        jobId=payload["job_id"],
        taskId=payload.get("task_id"),
        dispatchedAt=payload["dispatched_at"],
    )


@router.post("/jobs/{job_id}/pause", response_model=SchedulerDispatchResponse)
def pause_scheduler_job(
    job_id: str,
    _: ActorContext = Depends(require_super_admin),
    service: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerDispatchResponse:
    if not service.pause_job(job_id=job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduler job not found.")
    return SchedulerDispatchResponse(jobId=job_id, taskId=None, dispatchedAt=datetime.now(UTC))


@router.post("/jobs/{job_id}/resume", response_model=SchedulerDispatchResponse)
def resume_scheduler_job(
    job_id: str,
    _: ActorContext = Depends(require_super_admin),
    service: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerDispatchResponse:
    if not service.resume_job(job_id=job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduler job not found.")
    return SchedulerDispatchResponse(jobId=job_id, taskId=None, dispatchedAt=datetime.now(UTC))


@router.get("/health", response_model=SchedulerHealthResponse)
def scheduler_health(
    _: ActorContext = Depends(require_super_admin),
    service: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerHealthResponse:
    payload = service.health()
    return SchedulerHealthResponse(
        brokerOk=bool(payload["broker_ok"]),
        brokerError=payload.get("broker_error"),
        totalJobs=int(payload["total_jobs"]),
        pausedJobs=int(payload["paused_jobs"]),
        latestFinishedAt=payload.get("latest_finished_at"),
        timestamp=payload["timestamp"],
    )
