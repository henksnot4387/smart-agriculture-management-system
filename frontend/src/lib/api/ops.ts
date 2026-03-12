import type { OpsCatalogPayload, OpsLivePayload, OpsTrendsPayload } from "@/src/types/ops";

export class OpsApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "OpsApiError";
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
      // keep fallback message
    }
    throw new OpsApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchOpsCatalog(lookbackHours = 24): Promise<OpsCatalogPayload> {
  const params = new URLSearchParams({ lookbackHours: String(lookbackHours) });
  const response = await fetch(`/api/ops/catalog?${params.toString()}`, {
    cache: "no-store",
    credentials: "include",
  });
  return readJson<OpsCatalogPayload>(response, "加载参数目录失败。");
}

export async function fetchOpsLive(lookbackHours = 24): Promise<OpsLivePayload> {
  const params = new URLSearchParams({ lookbackHours: String(lookbackHours) });
  const response = await fetch(`/api/ops/live?${params.toString()}`, {
    cache: "no-store",
    credentials: "include",
  });
  return readJson<OpsLivePayload>(response, "加载运营实时数据失败。");
}

export async function fetchOpsTrends(hours = 24): Promise<OpsTrendsPayload> {
  const params = new URLSearchParams({ hours: String(hours) });
  const response = await fetch(`/api/ops/trends?${params.toString()}`, {
    cache: "no-store",
    credentials: "include",
  });
  return readJson<OpsTrendsPayload>(response, "加载运营趋势失败。");
}
