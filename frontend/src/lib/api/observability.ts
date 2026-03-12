import type {
  ObservabilityErrorsPayload,
  ObservabilityOverviewPayload,
  ObservabilitySlowRequestsPayload,
  ObservabilityTaskFailuresPayload,
} from "@/src/types/observability";

export class ObservabilityApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ObservabilityApiError";
    this.status = status;
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const raw = await response.text();
  let parsed: unknown = null;
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const detail =
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof (parsed as { detail?: unknown }).detail === "string"
        ? String((parsed as { detail: string }).detail)
        : `请求失败（HTTP ${response.status}）`;
    throw new ObservabilityApiError(detail, response.status);
  }

  return parsed as T;
}

export async function fetchObservabilityOverview(hours = 24): Promise<ObservabilityOverviewPayload> {
  const boundedHours = Math.min(168, Math.max(1, Math.trunc(hours)));
  const response = await fetch(`/api/admin/observability/overview?hours=${boundedHours}`, {
    method: "GET",
    cache: "no-store",
  });
  return parseJson<ObservabilityOverviewPayload>(response);
}

export async function fetchObservabilityErrors(
  hours = 24,
  limit = 100,
): Promise<ObservabilityErrorsPayload> {
  const boundedHours = Math.min(168, Math.max(1, Math.trunc(hours)));
  const boundedLimit = Math.min(500, Math.max(1, Math.trunc(limit)));
  const response = await fetch(
    `/api/admin/observability/errors?hours=${boundedHours}&limit=${boundedLimit}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );
  return parseJson<ObservabilityErrorsPayload>(response);
}

export async function fetchObservabilitySlowRequests(
  hours = 24,
  limit = 100,
): Promise<ObservabilitySlowRequestsPayload> {
  const boundedHours = Math.min(168, Math.max(1, Math.trunc(hours)));
  const boundedLimit = Math.min(500, Math.max(1, Math.trunc(limit)));
  const response = await fetch(
    `/api/admin/observability/slow-requests?hours=${boundedHours}&limit=${boundedLimit}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );
  return parseJson<ObservabilitySlowRequestsPayload>(response);
}

export async function fetchObservabilityTaskFailures(
  hours = 24,
  limit = 20,
): Promise<ObservabilityTaskFailuresPayload> {
  const boundedHours = Math.min(168, Math.max(1, Math.trunc(hours)));
  const boundedLimit = Math.min(200, Math.max(1, Math.trunc(limit)));
  const response = await fetch(
    `/api/admin/observability/task-failures?hours=${boundedHours}&limit=${boundedLimit}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );
  return parseJson<ObservabilityTaskFailuresPayload>(response);
}
