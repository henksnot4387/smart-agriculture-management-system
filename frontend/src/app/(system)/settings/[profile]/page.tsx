import { auth } from "@/auth";
import { SettingsProfileConsole } from "@/src/components/settings/settings-profile-console";
import type { SettingsProfileKey } from "@/src/types/settings";
import { redirect } from "next/navigation";

const slugToProfile: Record<string, SettingsProfileKey> = {
  horticulture: "horticulture",
  "plant-protection": "plant_protection",
  climate: "climate",
  fertigation: "fertigation",
};

export default async function SettingsProfilePage({
  params,
}: {
  params: Promise<{ profile: string }>;
}) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }
  const role = String(session.user.role || "").toUpperCase();
  if (!["SUPER_ADMIN", "ADMIN"].includes(role)) {
    redirect("/dashboard");
  }

  const { profile } = await params;
  const mapped = slugToProfile[profile];
  if (!mapped) {
    redirect("/settings");
  }
  return <SettingsProfileConsole profile={mapped} />;
}
