import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { getBackendPublicBaseUrl, toWebSocketBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getBrowserWebSocketBaseUrl(request: NextRequest) {
  const explicitPublicBaseUrl = (process.env.BACKEND_PUBLIC_BASE_URL || "").trim();
  if (explicitPublicBaseUrl) {
    return toWebSocketBaseUrl(explicitPublicBaseUrl);
  }

  const requestOrigin = (request.nextUrl.origin || "").trim();
  if (requestOrigin) {
    return toWebSocketBaseUrl(requestOrigin);
  }

  return toWebSocketBaseUrl(getBackendPublicBaseUrl("vision websocket"));
}

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const wsBaseUrl = getBrowserWebSocketBaseUrl(request);
  const params = new URLSearchParams();
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    params.set("token", apiToken);
  }

  const url = `${wsBaseUrl}/api/ws/vision/tasks${params.toString() ? `?${params.toString()}` : ""}`;
  return NextResponse.json({ url });
}
