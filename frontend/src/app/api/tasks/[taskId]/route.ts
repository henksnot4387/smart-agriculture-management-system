import { NextRequest, NextResponse } from "next/server";

import { ensureSessionRole, getApiBaseUrl, getBackendHeaders } from "@/src/app/api/tasks/_lib/proxy";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Params = { params: Promise<{ taskId: string }> };

export async function GET(request: NextRequest, { params }: Params) {
  const gate = await ensureSessionRole(["SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"]);
  if (!gate.ok) {
    return gate.response;
  }
  const resolved = await params;
  const search = request.nextUrl.searchParams.toString();
  const url = `${getApiBaseUrl()}/api/tasks/${encodeURIComponent(resolved.taskId)}${search ? `?${search}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: getBackendHeaders(gate.role, gate.userId),
    cache: "no-store",
  });
  const rawBody = await response.text();
  return new NextResponse(rawBody, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json",
    },
  });
}
