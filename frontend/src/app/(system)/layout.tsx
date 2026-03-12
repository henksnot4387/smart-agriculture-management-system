import { auth } from "@/auth";
import { AppShell } from "@/src/components/layout/app-shell";
import { redirect } from "next/navigation";

export default async function SystemLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  return (
    <AppShell
      user={{
        email: session.user.email ?? "unknown@example.local",
        role: session.user.role,
      }}
    >
      {children}
    </AppShell>
  );
}
