import { auth } from "@/auth";
import { SchedulerConsole } from "@/src/components/scheduler/scheduler-console";
import { redirect } from "next/navigation";

export default async function SchedulerPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  if ((session.user.role || "").toUpperCase() !== "SUPER_ADMIN") {
    redirect("/dashboard");
  }

  return <SchedulerConsole />;
}
