"use client";

import "@ant-design/v5-patch-for-react-19";
import { App, ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";

import { PropsWithChildren } from "react";

dayjs.locale("zh-cn");

export function AppProvider({ children }: PropsWithChildren) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#0f766e",
          borderRadius: 14,
          colorBgLayout: "#f4f7f0",
          colorText: "#1f2937",
          fontFamily:
            '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", sans-serif',
        },
        components: {
          Layout: {
            headerBg: "rgba(255,255,255,0.88)",
            siderBg: "#ffffff",
            bodyBg: "#f4f7f0",
          },
          Menu: {
            itemSelectedBg: "rgba(15, 118, 110, 0.12)",
            itemSelectedColor: "#0f766e",
            itemHoverColor: "#0f766e",
            itemBorderRadius: 12,
          },
          Card: {
            borderRadiusLG: 20,
          },
        },
      }}
    >
      <App>{children}</App>
    </ConfigProvider>
  );
}
