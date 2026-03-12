import { NextRequest } from "next/server";

import { ensureSuperAdminSession, proxyPost } from "@/src/app/api/admin/scheduler/_lib/proxy";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function POST(_: NextRequest, context: { params: Promise<{ jobId: string }> }) {
  const params = await context.params;
  const gate = await ensureSuperAdminSession();
  if (!gate.ok) {
    return gate.response;
  }
  return proxyPost(
    `/api/admin/scheduler/jobs/${encodeURIComponent(params.jobId)}/run`,
    gate.role || "SUPER_ADMIN",
    gate.userId || "",
  );
}
