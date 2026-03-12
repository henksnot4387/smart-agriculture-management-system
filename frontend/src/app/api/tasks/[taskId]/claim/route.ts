import { ensureSessionRole, proxyPost } from "@/src/app/api/tasks/_lib/proxy";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Params = { params: Promise<{ taskId: string }> };

export async function POST(_: Request, { params }: Params) {
  const gate = await ensureSessionRole(["WORKER"]);
  if (!gate.ok) {
    return gate.response;
  }
  const resolved = await params;
  return proxyPost(`/api/tasks/${encodeURIComponent(resolved.taskId)}/claim`, gate.role, gate.userId, {});
}
