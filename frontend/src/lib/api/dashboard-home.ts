import type { DashboardHomePayload, DashboardRange, SensorDashboardPayload, GreenhouseOverviewItem } from "@/src/types/sensor";

export class DashboardApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "DashboardApiError";
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
      // Ignore JSON parse failures and use fallback message.
    }
    throw new DashboardApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export async function fetchDashboardHome(range: DashboardRange, signal?: AbortSignal): Promise<DashboardHomePayload> {
  const params = new URLSearchParams({ range });

  const [dashboardResponse, zonesResponse] = await Promise.all([
    fetch(`/api/dashboard/sensor?${params.toString()}`, {
      cache: "no-store",
      signal,
      credentials: "include",
    }),
    fetch(`/api/dashboard/zones?${params.toString()}`, {
      cache: "no-store",
      signal,
      credentials: "include",
    }),
  ]);

  const [dashboard, zonesPayload] = await Promise.all([
    readJson<SensorDashboardPayload>(dashboardResponse, "加载首页概览失败。"),
    readJson<{ items: GreenhouseOverviewItem[] }>(zonesResponse, "加载温室分区概览失败。"),
  ]);

  return {
    dashboard,
    zones: zonesPayload.items,
  };
}

export async function triggerDashboardSync(signal?: AbortSignal): Promise<void> {
  const response = await fetch("/api/dashboard/sync", {
    method: "POST",
    cache: "no-store",
    signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });

  await readJson<{ ok: boolean }>(response, "触发数据同步失败。");
}
