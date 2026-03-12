import type {
  ApproveTaskRequest,
  AssignedToFilter,
  CompleteTaskRequest,
  TaskAssigneeListPayload,
  TaskDetailPayload,
  TaskListPayload,
  TaskSource,
  TaskStatus,
  TaskTransitionPayload,
} from "@/src/types/task";

export class TaskApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "TaskApiError";
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
      // Ignore parse errors and keep fallback.
    }
    throw new TaskApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchTasks(params?: {
  status?: TaskStatus;
  source?: TaskSource;
  assignedTo?: AssignedToFilter;
  limit?: number;
  signal?: AbortSignal;
}): Promise<TaskListPayload> {
  const search = new URLSearchParams();
  if (params?.status) {
    search.set("status", params.status);
  }
  if (params?.source) {
    search.set("source", params.source);
  }
  search.set("assignedTo", params?.assignedTo || "all");
  search.set("limit", String(Math.max(1, Math.min(params?.limit ?? 50, 200))));

  const response = await fetch(`/api/tasks?${search.toString()}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal: params?.signal,
  });
  return readJson<TaskListPayload>(response, "加载任务列表失败。");
}

export async function fetchTaskDetail(taskId: string, signal?: AbortSignal): Promise<TaskDetailPayload> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<TaskDetailPayload>(response, "加载任务详情失败。");
}

export async function fetchTaskAssignees(signal?: AbortSignal): Promise<TaskAssigneeListPayload> {
  const response = await fetch("/api/tasks/assignees", {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<TaskAssigneeListPayload>(response, "加载工人列表失败。");
}

export async function approveTask(taskId: string, payload: ApproveTaskRequest): Promise<TaskTransitionPayload> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/approve`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<TaskTransitionPayload>(response, "审批任务失败。");
}

export async function claimTask(taskId: string): Promise<TaskTransitionPayload> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/claim`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  return readJson<TaskTransitionPayload>(response, "接单失败。");
}

export async function startTask(taskId: string): Promise<TaskTransitionPayload> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/start`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  return readJson<TaskTransitionPayload>(response, "任务开工失败。");
}

export async function completeTask(taskId: string, payload: CompleteTaskRequest): Promise<TaskTransitionPayload> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/complete`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<TaskTransitionPayload>(response, "任务完工失败。");
}
