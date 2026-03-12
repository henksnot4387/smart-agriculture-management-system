import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("dashboard sync proxy");
}

function getAdminToken() {
  return (process.env.BACKEND_ADMIN_TOKEN || "").trim();
}

export async function POST() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }
  if (!["ADMIN", "EXPERT"].includes(session.user.role)) {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/integrations/hoogendoorn/sync`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(getAdminToken() ? { "X-Admin-Token": getAdminToken() } : {}),
      },
      cache: "no-store",
      body: JSON.stringify({}),
    });

    const rawBody = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";

    if (!response.ok) {
      return new NextResponse(rawBody || JSON.stringify({ detail: "Failed to trigger dashboard sync." }), {
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
        detail: error instanceof Error ? error.message : "Dashboard sync proxy request failed.",
      },
      { status: 502 },
    );
  }
}
