"use client";

import { ProLayout } from "@ant-design/pro-components";
import type { ProSettings } from "@ant-design/pro-components";
import { Space, Typography } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PropsWithChildren, useMemo, useState, useSyncExternalStore } from "react";

import { AppHeader } from "@/src/components/layout/app-header";
import { getPageMeta, systemMenuItems } from "@/src/lib/navigation/menu";

type AppShellProps = PropsWithChildren<{
  user: {
    email: string;
    role: string;
  };
}>;

const settings: Partial<ProSettings> = {
  fixSiderbar: true,
  fixedHeader: true,
  layout: "side",
  navTheme: "light",
  colorPrimary: "#0f766e",
};

const noopSubscribe = () => () => {};

function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

export function AppShell({ user, children }: AppShellProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const hydrated = useHydrated();
  const pageMeta = useMemo(() => getPageMeta(pathname), [pathname]);
  const normalizedRole = String(user.role).toUpperCase();
  const menuRoutes = useMemo(() => {
    return systemMenuItems.filter((item) => {
      if (item.key === "settings-group") {
        return normalizedRole !== "WORKER";
      }
      if (item.path === "/scheduler") {
        return normalizedRole === "SUPER_ADMIN";
      }
      if (item.path === "/observability") {
        return normalizedRole === "SUPER_ADMIN";
      }
      if (item.path === "/expert") {
        return normalizedRole !== "WORKER";
      }
      if (item.path === "/worker") {
        return normalizedRole === "WORKER";
      }
      if (item.path === "/tasks") {
        return normalizedRole !== "WORKER";
      }
      return true;
    });
  }, [normalizedRole]);

  // ProLayout injects responsive class names based on window width.
  // Render it only after client mount to avoid SSR/client hydration mismatch.
  if (!hydrated) {
    return <div style={{ minHeight: "100vh", background: "#f4f7f0" }}>{children}</div>;
  }

  return (
    <ProLayout
      {...settings}
      collapsed={collapsed}
      onCollapse={setCollapsed}
      title="智慧农业管理系统"
      logo={<div style={{ display: "grid", placeItems: "center", width: 32, height: 32, borderRadius: 10, background: "linear-gradient(135deg, #0f766e, #0f8f85)", color: "#fff", fontWeight: 700 }}>智</div>}
      location={{ pathname }}
      route={{ routes: menuRoutes }}
      menu={{ locale: false }}
      headerTitleRender={(logo, title) => (
        <Link href="/dashboard" style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          {logo}
          <Space direction="vertical" size={0} style={{ minWidth: 0 }}>
            <Typography.Text strong style={{ fontSize: 16, color: "#0f172a", lineHeight: 1.2 }}>
              {title}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12, lineHeight: 1.2 }}>
              温室数据、识别、任务与协同一体化
            </Typography.Text>
          </Space>
        </Link>
      )}
      menuItemRender={(item, dom) => {
        if (!item.path) {
          return dom;
        }
        return <Link href={item.path}>{dom}</Link>;
      }}
      actionsRender={() => [<AppHeader key="app-header" user={user} />]}
      contentStyle={{ padding: 24, minHeight: "calc(100vh - 56px)" }}
      headerContentRender={() => (
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
          <Typography.Text strong style={{ color: "#0f172a" }}>
            {pageMeta.title}
          </Typography.Text>
        </div>
      )}
    >
      {children}
    </ProLayout>
  );
}
