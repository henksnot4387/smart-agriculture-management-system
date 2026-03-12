import { auth } from "@/auth";
import { ExpertConsole } from "@/src/components/tasks/expert-console";
import { redirect } from "next/navigation";

export default async function ExpertPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }
  const role = String(session.user.role || "").toUpperCase();
  if (!["SUPER_ADMIN", "ADMIN", "EXPERT"].includes(role)) {
    redirect("/dashboard");
  }
  return <ExpertConsole userRole={role} />;
}
