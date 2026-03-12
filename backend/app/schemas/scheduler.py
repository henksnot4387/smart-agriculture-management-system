from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SchedulerJob(BaseModel):
    jobId: str
    taskName: str
    name: str
    description: str
    scheduleType: str
    scheduleValue: str
    isPaused: bool
    lastStatus: str | None = None
    lastMessage: str | None = None
    lastError: str | None = None
    lastRunStartedAt: datetime | None = None
    lastRunFinishedAt: datetime | None = None
    lastDurationMs: int | None = None
    nextRunAt: datetime | None = None


class SchedulerRun(BaseModel):
    id: int
    jobId: str
    trigger: str
    status: str
    message: str | None = None
    error: str | None = None
    startedAt: datetime
    finishedAt: datetime | None = None
    durationMs: int | None = None


class SchedulerJobsResponse(BaseModel):
    jobs: list[SchedulerJob]


class SchedulerRunsResponse(BaseModel):
    runs: list[SchedulerRun]


class SchedulerDispatchResponse(BaseModel):
    jobId: str
    taskId: str | None = None
    dispatchedAt: datetime


class SchedulerHealthResponse(BaseModel):
    brokerOk: bool
    brokerError: str | None = None
    totalJobs: int
    pausedJobs: int
    latestFinishedAt: datetime | None = None
    timestamp: datetime
