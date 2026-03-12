import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getBackendHeaders() {
  const headers: HeadersInit = { Accept: "application/json" };
  const token = process.env.BACKEND_API_TOKEN;
  if (token) {
    headers["X-API-Token"] = token;
  }
  return headers;
}

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const query = request.nextUrl.search || "";
  const url = `${getBackendInternalBaseUrl("ops catalog proxy")}/api/ops/catalog${query}`;
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: getBackendHeaders(),
      cache: "no-store",
    });
    const raw = await response.text();
    return new NextResponse(raw || "{}", {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Ops catalog proxy failed." },
      { status: 502 },
    );
  }
}
