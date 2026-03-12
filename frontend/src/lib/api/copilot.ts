import type {
  CopilotRecommendationConfirmPayload,
  CopilotRecommendationConfirmRequest,
  CopilotRecommendationGeneratePayload,
  CopilotRecommendationGenerateRequest,
  CopilotRecommendationListPayload,
  CopilotRecommendationDraftStatus,
  CopilotSummaryPayload,
  KnowledgeListPayload,
  KnowledgeMetaPayload,
} from "@/src/types/copilot";

export class CopilotApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "CopilotApiError";
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
    throw new CopilotApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchCopilotSummary(
  hours = 24,
  signal?: AbortSignal,
  options?: { mode?: "cached" | "refresh"; zone?: string },
): Promise<CopilotSummaryPayload> {
  const boundedHours = Math.max(1, Math.min(hours, 168));
  const search = new URLSearchParams();
  search.set("hours", String(boundedHours));
  search.set("mode", options?.mode || "cached");
  if (options?.zone) {
    search.set("zone", options.zone);
  }
  const response = await fetch(`/api/ai-insights/summary?${search.toString()}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<CopilotSummaryPayload>(response, "加载 AI 智能解析失败。");
}

export async function fetchKnowledgeMeta(signal?: AbortSignal): Promise<KnowledgeMetaPayload> {
  const response = await fetch("/api/ai-insights/knowledge/meta", {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal,
  });
  return readJson<KnowledgeMetaPayload>(response, "加载知识库元信息失败。");
}

export async function fetchKnowledgeItems(params?: {
  category?: string;
  q?: string;
  keywords?: string[];
  limit?: number;
  signal?: AbortSignal;
}): Promise<KnowledgeListPayload> {
  const search = new URLSearchParams();
  if (params?.category) {
    search.set("category", params.category);
  }
  if (params?.q) {
    search.set("q", params.q);
  }
  if (params?.keywords && params.keywords.length > 0) {
    search.set("keywords", params.keywords.join(","));
  }
  search.set("limit", String(Math.max(1, Math.min(params?.limit ?? 30, 200))));

  const response = await fetch(`/api/ai-insights/knowledge?${search.toString()}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal: params?.signal,
  });
  return readJson<KnowledgeListPayload>(response, "加载知识库内容失败。");
}

export async function fetchCopilotRecommendations(params?: {
  limit?: number;
  status?: CopilotRecommendationDraftStatus;
  signal?: AbortSignal;
}): Promise<CopilotRecommendationListPayload> {
  const search = new URLSearchParams();
  const limit = Math.max(1, Math.min(params?.limit ?? 20, 100));
  search.set("limit", String(limit));
  if (params?.status) {
    search.set("status", params.status);
  }
  const response = await fetch(`/api/ai-insights/recommendations?${search.toString()}`, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    signal: params?.signal,
  });
  return readJson<CopilotRecommendationListPayload>(response, "加载 AI 建议历史失败。");
}

export async function generateCopilotRecommendations(
  payload: CopilotRecommendationGenerateRequest,
  signal?: AbortSignal,
): Promise<CopilotRecommendationGeneratePayload> {
  const response = await fetch("/api/ai-insights/recommendations", {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<CopilotRecommendationGeneratePayload>(response, "生成 AI 建议失败。");
}

export async function confirmCopilotRecommendations(
  payload: CopilotRecommendationConfirmRequest,
  signal?: AbortSignal,
): Promise<CopilotRecommendationConfirmPayload> {
  const response = await fetch("/api/ai-insights/recommendations/confirm", {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<CopilotRecommendationConfirmPayload>(response, "确认入库失败。");
}
