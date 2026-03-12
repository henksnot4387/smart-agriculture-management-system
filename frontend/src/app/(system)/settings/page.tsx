import { auth } from "@/auth";
import { SettingsOverview } from "@/src/components/settings/settings-overview";
import { redirect } from "next/navigation";

export default async function SettingsPage() {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }
  const role = String(session.user.role || "").toUpperCase();
  if (!["SUPER_ADMIN", "ADMIN"].includes(role)) {
    redirect("/dashboard");
  }
  return <SettingsOverview />;
}
