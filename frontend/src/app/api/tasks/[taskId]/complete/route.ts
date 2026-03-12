import { NextRequest } from "next/server";

import { ensureSessionRole, proxyPost } from "@/src/app/api/tasks/_lib/proxy";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Params = { params: Promise<{ taskId: string }> };

export async function POST(request: NextRequest, { params }: Params) {
  const gate = await ensureSessionRole(["WORKER"]);
  if (!gate.ok) {
    return gate.response;
  }
  let payload: unknown = {};
  try {
    payload = await request.json();
  } catch {
    payload = {};
  }
  const resolved = await params;
  return proxyPost(`/api/tasks/${encodeURIComponent(resolved.taskId)}/complete`, gate.role, gate.userId, payload);
}
