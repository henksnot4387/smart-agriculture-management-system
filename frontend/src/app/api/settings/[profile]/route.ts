import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

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

export async function GET(_: NextRequest, context: { params: Promise<{ profile: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { profile } = await context.params;
  try {
    const response = await fetch(`${getBackendInternalBaseUrl("settings proxy")}/api/settings/${profile}`, {
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
      { detail: error instanceof Error ? error.message : "Settings profile proxy failed." },
      { status: 502 },
    );
  }
}

export async function POST(request: NextRequest, context: { params: Promise<{ profile: string }> }) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const { profile } = await context.params;
  const body = await request.text();
  try {
    const response = await fetch(`${getBackendInternalBaseUrl("settings proxy")}/api/settings/${profile}`, {
      method: "POST",
      headers: { ...getHeaders(session), "content-type": "application/json" },
      body,
      cache: "no-store",
    });
    const raw = await response.text();
    return new NextResponse(raw || "{}", {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Settings profile save proxy failed." },
      { status: 502 },
    );
  }
}
