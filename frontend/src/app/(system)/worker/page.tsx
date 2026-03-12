import { auth } from "@/auth";
import { WorkerConsole } from "@/src/components/tasks/worker-console";
import { redirect } from "next/navigation";

export default async function WorkerPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }
  const role = String(session.user.role || "").toUpperCase();
  if (role !== "WORKER") {
    redirect("/dashboard");
  }
  return <WorkerConsole userEmail={session.user.email || "worker@example.local"} />;
}
