import { ensureSuperAdminSession, proxyGet } from "@/src/app/api/admin/observability/_lib/proxy";
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: NextRequest) {
  const gate = await ensureSuperAdminSession();
  if (!gate.ok) {
    return gate.response;
  }

  const hours = request.nextUrl.searchParams.get("hours") ?? "24";
  const limit = request.nextUrl.searchParams.get("limit") ?? "100";
  return proxyGet(
    `/api/admin/observability/slow-requests?hours=${encodeURIComponent(hours)}&limit=${encodeURIComponent(limit)}`,
    gate.role || "SUPER_ADMIN",
    gate.userId || "",
  );
}
