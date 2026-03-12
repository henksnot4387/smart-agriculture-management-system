"use client";

import { ArrowRightOutlined, BookOutlined, FileSearchOutlined, RobotOutlined } from "@ant-design/icons";
import { Button, Col, Row, Space, Steps, Typography } from "antd";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import Link from "next/link";

const cards = [
  {
    title: "AI 建议草稿与任务入库",
    description: "生成建议草稿并人工确认后写入任务中心，避免误派工。",
    path: "/ai-insights/recommendations",
    icon: <RobotOutlined />,
    color: "rgba(15, 118, 110, 0.10)",
  },
  {
    title: "AI 智能解析",
    description: "基于真实温湿度/EC/pH 与病害结果输出双层专业解析。",
    path: "/ai-insights/summary",
    icon: <FileSearchOutlined />,
    color: "rgba(3, 105, 161, 0.10)",
  },
  {
    title: "本地知识库（分类 + 关键词）",
    description: "按分类和关键词检索知识，查看来源、采集状态与落地建议。",
    path: "/ai-insights/knowledge",
    icon: <BookOutlined />,
    color: "rgba(132, 204, 22, 0.14)",
  },
];

export default function AIInsightsOverviewPage() {
  return (
    <PageContainer title="智能建议">
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <ProCard bordered title="推荐使用流程">
          <Steps
            responsive
            current={-1}
            items={[
              { title: "先看智能解析", description: "判断近24小时关键风险" },
              { title: "再生成草稿", description: "人工确认后再入库任务" },
              { title: "最后查知识", description: "给专家/工人补充依据" },
            ]}
          />
        </ProCard>

        <Row gutter={[12, 12]}>
          {cards.map((card) => (
            <Col xs={24} lg={8} key={card.path}>
              <ProCard bordered style={{ height: "100%" }}>
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <div
                    style={{
                      width: 42,
                      height: 42,
                      borderRadius: 12,
                      display: "grid",
                      placeItems: "center",
                      background: card.color,
                      fontSize: 18,
                    }}
                  >
                    {card.icon}
                  </div>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {card.title}
                  </Typography.Title>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0, minHeight: 44 }}>
                    {card.description}
                  </Typography.Paragraph>
                  <Link href={card.path}>
                    <Button type="primary" icon={<ArrowRightOutlined />}>
                      进入模块
                    </Button>
                  </Link>
                </Space>
              </ProCard>
            </Col>
          ))}
        </Row>
      </Space>
    </PageContainer>
  );
}
