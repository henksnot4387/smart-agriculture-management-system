"use client";

import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import { LockOutlined, LoginOutlined, MailOutlined } from "@ant-design/icons";
import { signIn } from "next-auth/react";
import { useState } from "react";

type LoginFormValues = {
  email: string;
  password: string;
};

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (values: LoginFormValues) => {
    setError(null);
    setIsSubmitting(true);

    const result = await signIn("credentials", {
      email: values.email,
      password: values.password,
      redirect: false,
      callbackUrl: "/dashboard",
    });

    setIsSubmitting(false);

    if (!result || result.error) {
      setError("账号或密码错误，请重新输入。");
      return;
    }

    window.location.assign("/dashboard");
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
        background:
          "radial-gradient(circle at top left, rgba(15,118,110,0.18), transparent 28%), radial-gradient(circle at bottom right, rgba(245,158,11,0.16), transparent 26%), linear-gradient(180deg, #f5f7f2 0%, #eef4f2 100%)",
      }}
    >
      <Card
        variant="borderless"
        style={{
          width: "100%",
          maxWidth: 520,
          borderRadius: 24,
          boxShadow: "0 24px 60px -36px rgba(15, 118, 110, 0.48)",
          background: "rgba(255,255,255,0.88)",
          backdropFilter: "blur(16px)",
        }}
        styles={{ body: { padding: 32 } }}
      >
        <Space direction="vertical" size={24} style={{ width: "100%" }}>
          <div>
            <Typography.Text type="secondary">智慧农业管理系统</Typography.Text>
            <Typography.Title level={1} style={{ marginTop: 8, marginBottom: 12, fontSize: 40 }}>
              登录系统
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 16 }}>
              面向温室运营、专家审批和工人执行的统一农业管理入口。
            </Typography.Paragraph>
          </div>

          {error ? <Alert type="warning" showIcon message={error} /> : null}

          <Form<LoginFormValues>
            layout="vertical"
            initialValues={{ email: "", password: "" }}
            onFinish={handleSubmit}
          >
            <Form.Item
              label="邮箱账号"
              name="email"
              rules={[
                { required: true, message: "请输入邮箱账号。" },
                { type: "email", message: "邮箱格式不正确。" },
              ]}
            >
              <Input
                size="large"
                prefix={<MailOutlined />}
                placeholder="请输入邮箱账号"
                autoComplete="email"
              />
            </Form.Item>

            <Form.Item
              label="登录密码"
              name="password"
              rules={[{ required: true, message: "请输入登录密码。" }]}
            >
              <Input.Password
                size="large"
                prefix={<LockOutlined />}
                placeholder="请输入密码"
                autoComplete="current-password"
              />
            </Form.Item>

            <Button
              type="primary"
              htmlType="submit"
              size="large"
              icon={<LoginOutlined />}
              loading={isSubmitting}
              block
            >
              {isSubmitting ? "登录中..." : "登录系统"}
            </Button>
          </Form>
        </Space>
      </Card>
    </main>
  );
}
