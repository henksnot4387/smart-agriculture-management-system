import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import "antd/dist/reset.css";
import "@/src/app/globals.css";

import { AppProvider } from "@/src/components/providers/app-provider";

export const metadata: Metadata = {
  title: "智慧农业管理系统",
  description: "面向现代温室的多模态智慧农业运营平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        style={{
          fontFamily:
            '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif',
        }}
      >
        <AntdRegistry>
          <AppProvider>{children}</AppProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
