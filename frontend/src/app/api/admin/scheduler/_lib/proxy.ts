import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export function getApiBaseUrl() {
  return getBackendInternalBaseUrl("scheduler proxy");
}

export async function ensureSuperAdminSession() {
  const session = await auth();
  if (!session?.user) {
    return {
      ok: false,
      response: NextResponse.json({ detail: "Unauthorized" }, { status: 401 }),
      role: null,
      userId: null,
    } as const;
  }

  if ((session.user.role || "").toUpperCase() !== "SUPER_ADMIN") {
    return {
      ok: false,
      response: NextResponse.json({ detail: "Forbidden" }, { status: 403 }),
      role: session.user.role,
      userId: session.user.id || null,
    } as const;
  }

  if (!session.user.id) {
    return {
      ok: false,
      response: NextResponse.json({ detail: "Unauthorized" }, { status: 401 }),
      role: session.user.role,
      userId: null,
    } as const;
  }

  return {
    ok: true,
    response: null,
    role: session.user.role,
    userId: session.user.id,
  } as const;
}

export function getBackendHeaders(role: string, userId: string) {
  const headers: HeadersInit = {
    Accept: "application/json",
    "X-User-Role": String(role || "").toUpperCase(),
    "X-User-Id": String(userId || ""),
  };
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  return headers;
}

export async function proxyGet(path: string, role: string, userId: string) {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "GET",
    headers: getBackendHeaders(role, userId),
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

export async function proxyPost(path: string, role: string, userId: string, body?: unknown) {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      ...getBackendHeaders(role, userId),
      "Content-Type": "application/json",
    },
    cache: "no-store",
    body: JSON.stringify(body ?? {}),
  });
  const rawBody = await response.text();
  return new NextResponse(rawBody, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json",
    },
  });
}
