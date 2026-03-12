import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("vision proxy");
}

function getBackendHeaders(userId?: string) {
  const headers: HeadersInit = {
    Accept: "application/json",
  };
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  if (userId) {
    headers["X-User-Id"] = userId;
  }
  return headers;
}

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const limit = request.nextUrl.searchParams.get("limit") || "20";
  const params = new URLSearchParams({ limit });

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/vision/tasks?${params.toString()}`, {
      method: "GET",
      headers: getBackendHeaders(),
      cache: "no-store",
    });

    const rawBody = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";
    return new NextResponse(rawBody, {
      status: response.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Vision tasks proxy request failed.",
      },
      { status: 502 },
    );
  }
}

export async function POST(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "Missing file field." }, { status: 422 });
  }

  const source = String(formData.get("source") || "MOBILE").trim().toUpperCase();
  const outbound = new FormData();
  outbound.append("file", file);

  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/vision/tasks?${new URLSearchParams({ source }).toString()}`,
      {
        method: "POST",
        headers: getBackendHeaders(session.user.id),
        body: outbound,
        cache: "no-store",
      },
    );

    const rawBody = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";
    return new NextResponse(rawBody, {
      status: response.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Vision task create proxy request failed.",
      },
      { status: 502 },
    );
  }
}
