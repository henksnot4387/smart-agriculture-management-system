import { NextRequest } from "next/server";

import { ensureSessionRole, proxyGet } from "@/src/app/api/tasks/_lib/proxy";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: NextRequest) {
  const gate = await ensureSessionRole(["SUPER_ADMIN", "ADMIN", "EXPERT"]);
  if (!gate.ok) {
    return gate.response;
  }
  return proxyGet(request, "/api/tasks/assignees", gate.role, gate.userId);
}
