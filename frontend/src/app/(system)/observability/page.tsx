import { auth } from "@/auth";
import { ObservabilityConsole } from "@/src/components/observability/observability-console";
import { redirect } from "next/navigation";

export default async function ObservabilityPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  const role = String(session.user.role || "").toUpperCase();
  if (role !== "SUPER_ADMIN") {
    redirect("/dashboard");
  }

  return <ObservabilityConsole />;
}
