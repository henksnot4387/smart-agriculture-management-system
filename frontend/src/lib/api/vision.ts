import type { VisionRuntimePayload, VisionTask, VisionTaskListPayload, VisionWsUrlPayload } from "@/src/types/vision";

export class VisionApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "VisionApiError";
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
    throw new VisionApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchVisionRuntime(signal?: AbortSignal): Promise<VisionRuntimePayload> {
  const response = await fetch("/api/vision/runtime", {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<VisionRuntimePayload>(response, "加载视觉运行状态失败。");
}

export async function fetchVisionTasks(limit = 20, signal?: AbortSignal): Promise<VisionTaskListPayload> {
  const response = await fetch(`/api/vision/tasks?limit=${Math.max(1, Math.min(limit, 100))}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<VisionTaskListPayload>(response, "加载识别任务列表失败。");
}

export async function fetchVisionTask(taskId: string, signal?: AbortSignal): Promise<VisionTask> {
  const response = await fetch(`/api/vision/tasks/${encodeURIComponent(taskId)}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<VisionTask>(response, "加载识别任务状态失败。");
}

export async function submitVisionTask(file: File, source = "MOBILE"): Promise<VisionTask> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source", source);

  const response = await fetch("/api/vision/tasks", {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    body: formData,
  });
  return readJson<VisionTask>(response, "提交识别任务失败。");
}

export async function fetchVisionWebSocketUrl(signal?: AbortSignal): Promise<string> {
  const response = await fetch("/api/vision/ws-url", {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  const payload = await readJson<VisionWsUrlPayload>(response, "获取实时推送连接地址失败。");
  if (!payload.url) {
    throw new VisionApiError("实时推送地址为空。", 500);
  }
  return payload.url;
}
