import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

const ALL_ROLES = ["SUPER_ADMIN", "ADMIN", "EXPERT", "WORKER"] as const;

type UserRole = (typeof ALL_ROLES)[number];

export function getApiBaseUrl() {
  return getBackendInternalBaseUrl("tasks proxy");
}

export async function ensureSessionRole(allowedRoles: UserRole[] = [...ALL_ROLES]) {
  const session = await auth();
  if (!session?.user) {
    return {
      ok: false,
      response: NextResponse.json({ detail: "Unauthorized" }, { status: 401 }),
      role: null,
      userId: null,
    } as const;
  }

  const role = String(session.user.role || "").toUpperCase() as UserRole;
  const userId = String(session.user.id || "");
  if (!ALL_ROLES.includes(role)) {
    return {
      ok: false,
      response: NextResponse.json({ detail: "Forbidden" }, { status: 403 }),
      role,
      userId,
    } as const;
  }
  if (!allowedRoles.includes(role)) {
    return {
      ok: false,
      response: NextResponse.json({ detail: "Forbidden" }, { status: 403 }),
      role,
      userId,
    } as const;
  }
  return {
    ok: true,
    response: null,
    role,
    userId,
  } as const;
}

export function getBackendHeaders(role: string, userId: string, withJson = false): HeadersInit {
  const headers: HeadersInit = {
    Accept: "application/json",
    "X-User-Role": role.toUpperCase(),
    "X-User-Id": userId,
  };
  if (withJson) {
    headers["Content-Type"] = "application/json";
  }
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  return headers;
}

export async function proxyGet(request: NextRequest, path: string, role: string, userId: string) {
  const search = request.nextUrl.searchParams.toString();
  const url = `${getApiBaseUrl()}${path}${search ? `?${search}` : ""}`;
  const response = await fetch(url, {
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

export async function proxyPost(
  path: string,
  role: string,
  userId: string,
  payload: unknown = {},
) {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: getBackendHeaders(role, userId, true),
    cache: "no-store",
    body: JSON.stringify(payload),
  });
  const rawBody = await response.text();
  return new NextResponse(rawBody, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "application/json",
    },
  });
}
