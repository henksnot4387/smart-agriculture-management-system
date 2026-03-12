"use client";

import { SettingOutlined } from "@ant-design/icons";
import { Button, Col, Row, Space, Tag, Typography } from "antd";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import Link from "next/link";

const settingModules = [
  {
    title: "园艺设置",
    path: "/settings/horticulture",
    description: "配置打叶、落蔓、绕头等园艺操作的自动触发任务策略。",
  },
  {
    title: "植保设置",
    path: "/settings/plant-protection",
    description: "配置打药、消毒、病害复检的自动触发任务策略。",
  },
  {
    title: "环控设置",
    path: "/settings/climate",
    description: "配置环控策略复核、执行器校准与巡检节奏。",
  },
  {
    title: "水肥设置",
    path: "/settings/fertigation",
    description: "配置施肥机、EC/pH 与灌溉执行的自动化任务策略。",
  },
];

export function SettingsOverview() {
  return (
    <PageContainer title="系统设置" subTitle="按业务域管理自动任务触发策略。">
      <Row gutter={[12, 12]}>
        {settingModules.map((item) => (
          <Col xs={24} md={12} key={item.path}>
            <ProCard bordered style={{ height: "100%" }}>
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                <Space>
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 10,
                      background: "rgba(15, 118, 110, 0.12)",
                      display: "grid",
                      placeItems: "center",
                    }}
                  >
                    <SettingOutlined />
                  </div>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {item.title}
                  </Typography.Title>
                </Space>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0, minHeight: 42 }}>
                  {item.description}
                </Typography.Paragraph>
                <Space>
                  <Tag color="processing">自动化任务</Tag>
                  <Tag color="default">人工触发</Tag>
                </Space>
                <Link href={item.path}>
                  <Button type="primary">进入配置</Button>
                </Link>
              </Space>
            </ProCard>
          </Col>
        ))}
      </Row>
    </PageContainer>
  );
}
