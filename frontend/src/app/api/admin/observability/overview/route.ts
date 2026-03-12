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
  return proxyGet(
    `/api/admin/observability/overview?hours=${encodeURIComponent(hours)}`,
    gate.role || "SUPER_ADMIN",
    gate.userId || "",
  );
}
