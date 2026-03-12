import { ensureSuperAdminSession, proxyGet } from "@/src/app/api/admin/scheduler/_lib/proxy";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  const gate = await ensureSuperAdminSession();
  if (!gate.ok) {
    return gate.response;
  }
  return proxyGet("/api/admin/scheduler/jobs", gate.role || "SUPER_ADMIN", gate.userId || "");
}
