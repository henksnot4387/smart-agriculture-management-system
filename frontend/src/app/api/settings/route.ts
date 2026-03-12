import { auth } from "@/auth";
import { NextResponse } from "next/server";

import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getHeaders(session: { user?: { role?: string | null; id?: string | null } } | null): HeadersInit {
  const headers: HeadersInit = { Accept: "application/json" };
  const token = process.env.BACKEND_API_TOKEN;
  if (token) {
    headers["X-API-Token"] = token;
  }
  if (session?.user?.role) {
    headers["X-User-Role"] = String(session.user.role);
  }
  if (session?.user?.id) {
    headers["X-User-Id"] = String(session.user.id);
  }
  return headers;
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  try {
    const response = await fetch(`${getBackendInternalBaseUrl("settings proxy")}/api/settings`, {
      method: "GET",
      headers: getHeaders(session),
      cache: "no-store",
    });
    const raw = await response.text();
    return new NextResponse(raw || "{}", {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Settings proxy request failed." },
      { status: 502 },
    );
  }
}
