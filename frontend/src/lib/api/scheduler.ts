import type {
  SchedulerDispatchPayload,
  SchedulerHealthPayload,
  SchedulerJobsPayload,
  SchedulerRunsPayload,
} from "@/src/types/scheduler";

export class SchedulerApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SchedulerApiError";
    this.status = status;
  }
}

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let message = fallback;
    try {
      const payload = (await response.json()) as { detail?: string; error?: string };
      message = payload.detail || payload.error || fallback;
    } catch {
      // Keep fallback when response body is not JSON.
    }
    throw new SchedulerApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchSchedulerJobs(signal?: AbortSignal): Promise<SchedulerJobsPayload> {
  const response = await fetch("/api/admin/scheduler/jobs", {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<SchedulerJobsPayload>(response, "加载调度任务失败。");
}

export async function fetchSchedulerRuns(limit = 100, signal?: AbortSignal): Promise<SchedulerRunsPayload> {
  const bounded = Math.max(1, Math.min(limit, 500));
  const response = await fetch(`/api/admin/scheduler/runs?limit=${bounded}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<SchedulerRunsPayload>(response, "加载执行历史失败。");
}

export async function fetchSchedulerHealth(signal?: AbortSignal): Promise<SchedulerHealthPayload> {
  const response = await fetch("/api/admin/scheduler/health", {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<SchedulerHealthPayload>(response, "加载调度健康状态失败。");
}

export async function runSchedulerJob(jobId: string): Promise<SchedulerDispatchPayload> {
  const response = await fetch(`/api/admin/scheduler/jobs/${encodeURIComponent(jobId)}/run`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
  });
  return readJson<SchedulerDispatchPayload>(response, "手动执行任务失败。");
}

export async function pauseSchedulerJob(jobId: string): Promise<SchedulerDispatchPayload> {
  const response = await fetch(`/api/admin/scheduler/jobs/${encodeURIComponent(jobId)}/pause`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
  });
  return readJson<SchedulerDispatchPayload>(response, "暂停任务失败。");
}

export async function resumeSchedulerJob(jobId: string): Promise<SchedulerDispatchPayload> {
  const response = await fetch(`/api/admin/scheduler/jobs/${encodeURIComponent(jobId)}/resume`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
  });
  return readJson<SchedulerDispatchPayload>(response, "恢复任务失败。");
}
