import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("vision file proxy");
}

type RouteContext = {
  params: Promise<{ filePath: string[] }>;
};

export async function GET(_: Request, context: RouteContext) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { filePath } = await context.params;
  if (!Array.isArray(filePath) || filePath.length === 0) {
    return NextResponse.json({ detail: "Missing file path." }, { status: 400 });
  }

  const backendPath = filePath.map((segment) => encodeURIComponent(segment)).join("/");

  try {
    const response = await fetch(`${getApiBaseUrl()}/files/${backendPath}`, {
      method: "GET",
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.json(
        { detail: `Upstream image fetch failed (${response.status}).` },
        { status: response.status },
      );
    }

    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") || "application/octet-stream";
    const cacheControl = response.headers.get("cache-control") || "private, max-age=60";

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "content-type": contentType,
        "cache-control": cacheControl,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Vision image proxy request failed.",
      },
      { status: 502 },
    );
  }
}
