"use client";

import { LogoutOutlined } from "@ant-design/icons";
import { Avatar, Button, Dropdown, Space, Typography } from "antd";
import { signOut } from "next-auth/react";

type AppHeaderProps = {
  user: {
    email: string;
    role: string;
  };
};

export function AppHeader({ user }: AppHeaderProps) {
  return (
    <Space size={14} align="center" wrap>
      <Dropdown
        menu={{
          items: [
            {
              key: "email",
              label: user.email,
              disabled: true,
            },
            {
              key: "role",
              label: `角色：${user.role}`,
              disabled: true,
            },
            {
              type: "divider",
            },
            {
              key: "logout",
              icon: <LogoutOutlined />,
              label: "退出登录",
              onClick: () => signOut({ callbackUrl: "/login" }),
            },
          ],
        }}
        trigger={["click"]}
      >
        <Button type="text" style={{ height: "auto", paddingInline: 8 }}>
          <Space size={10}>
            <Avatar style={{ backgroundColor: "#0f766e", flexShrink: 0 }}>
              {user.email.slice(0, 1).toUpperCase()}
            </Avatar>
            <div style={{ textAlign: "left", lineHeight: 1.2 }}>
              <Typography.Text strong style={{ display: "block", maxWidth: 180 }} ellipsis>
                {user.email}
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {user.role}
              </Typography.Text>
            </div>
          </Space>
        </Button>
      </Dropdown>
    </Space>
  );
}
