import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("vision runtime proxy");
}

function getBackendHeaders() {
  const headers: HeadersInit = {
    Accept: "application/json",
  };
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  return headers;
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/vision/runtime`, {
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
        detail: error instanceof Error ? error.message : "Vision runtime proxy request failed.",
      },
      { status: 502 },
    );
  }
}
