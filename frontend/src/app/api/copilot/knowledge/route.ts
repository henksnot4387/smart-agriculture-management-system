import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("copilot knowledge legacy proxy");
}

function legacyHeaders(contentType: string, response: globalThis.Response): HeadersInit {
  return {
    "content-type": contentType,
    Deprecation: response.headers.get("Deprecation") || "true",
    "X-API-Deprecated": response.headers.get("X-API-Deprecated") || "Use /api/ai-insights/*",
  };
}

function getBackendRequestHeaders(session: { user: { role?: string; id?: string } }): HeadersInit {
  const headers: HeadersInit = {
    Accept: "application/json",
    "X-User-Role": String(session.user.role || "").toUpperCase(),
    "X-User-Id": String(session.user.id || ""),
  };
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  return headers;
}

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const params = new URLSearchParams();
  for (const key of ["category", "q", "keywords", "limit"]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) params.set(key, value);
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/copilot/knowledge?${params.toString()}`, {
      method: "GET",
      headers: getBackendRequestHeaders(session),
      cache: "no-store",
    });
    const rawBody = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";
    return new NextResponse(rawBody, {
      status: response.status,
      headers: legacyHeaders(contentType, response),
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Knowledge proxy request failed.",
      },
      { status: 502 },
    );
  }
}
