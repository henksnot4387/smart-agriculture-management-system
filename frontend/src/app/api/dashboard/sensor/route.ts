import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("dashboard proxy");
}

function getBackendRequestHeaders() {
  const headers: HeadersInit = {
    Accept: "application/json",
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

  const range = request.nextUrl.searchParams.get("range") || "24h";
  const zone = request.nextUrl.searchParams.get("zone");

  const params = new URLSearchParams({ range });
  if (zone) {
    params.set("zone", zone);
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/sensor/dashboard?${params.toString()}`, {
      method: "GET",
      headers: getBackendRequestHeaders(),
      cache: "no-store",
    });

    const rawBody = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";

    if (!response.ok) {
      return new NextResponse(rawBody || JSON.stringify({ detail: "Failed to fetch dashboard data." }), {
        status: response.status,
        headers: {
          "content-type": contentType,
        },
      });
    }

    return new NextResponse(rawBody, {
      status: 200,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Dashboard proxy request failed.",
      },
      { status: 502 },
    );
  }
}
