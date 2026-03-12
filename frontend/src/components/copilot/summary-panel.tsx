"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Col, Empty, List, Row, Space, Table, Tag, Typography } from "antd";
import { ProCard } from "@ant-design/pro-components";

import { fetchCopilotSummary } from "@/src/lib/api/copilot";
import type { AIInsightSummaryPayload } from "@/src/types/copilot";

export function CopilotSummaryPanel() {
  const [summary, setSummary] = useState<AIInsightSummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async (mode: "cached" | "refresh") => {
    if (mode === "refresh") {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    try {
      const payload = await fetchCopilotSummary(24, undefined, { mode });
      setSummary(payload);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "加载 AI 智能解析失败。");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadSummary("cached");
  }, [loadSummary]);

  const riskColor = useMemo(() => {
    if (!summary) return "default";
    if (summary.executive.riskLevel === "HIGH") return "error";
    if (summary.executive.riskLevel === "MEDIUM") return "warning";
    return "success";
  }, [summary]);

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {error ? <Alert type="error" showIcon message="AI 智能解析加载失败" description={error} /> : null}

      <ProCard
        title="AI 智能解析（近24小时）"
        bordered
        loading={loading}
        extra={
          <Space size={8}>
            <Button loading={refreshing} onClick={() => void loadSummary("refresh")}>
              立即刷新
            </Button>
          </Space>
        }
      >
        {!summary ? (
          <Empty description="暂无智能解析数据" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Row gutter={[12, 12]}>
              <Col xs={24} xl={12}>
                <ProCard bordered title="管理层摘要">
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space wrap>
                      <Tag color={riskColor}>风险等级：{summary.executive.riskLevel}</Tag>
                      <Tag color={summary.meta.freshnessStatus === "STALE" ? "error" : summary.meta.freshnessStatus === "WARNING" ? "warning" : "success"}>
                        数据新鲜度：{summary.meta.freshnessStatus}
                      </Tag>
                      <Tag>{summary.meta.engineProvider.toUpperCase()}</Tag>
                    </Space>
                    <Typography.Title level={4} style={{ margin: 0 }}>
                      {summary.executive.headline}
                    </Typography.Title>
                    <List
                      size="small"
                      dataSource={summary.executive.keyFindings}
                      renderItem={(item) => <List.Item>{item}</List.Item>}
                    />
                  </Space>
                </ProCard>
              </Col>
              <Col xs={24} xl={12}>
                <ProCard bordered title="时间与来源">
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Typography.Text>页面刷新时间：{new Date(summary.meta.pageRefreshedAt).toLocaleString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" })}</Typography.Text>
                    <Typography.Text>数据最新采样时间（+08:00）：{summary.meta.latestSampleAtLocal || "--"}</Typography.Text>
                    <Typography.Text>数据来源：{summary.meta.source}</Typography.Text>
                    <Typography.Text>
                      引擎：{summary.meta.engineProvider}
                      {summary.meta.engineModel ? ` / ${summary.meta.engineModel}` : ""}
                    </Typography.Text>
                    {summary.meta.warningMessage ? (
                      <Alert type="warning" showIcon message={summary.meta.warningMessage} />
                    ) : null}
                  </Space>
                </ProCard>
              </Col>
            </Row>

            <ProCard title="专家解析" bordered>
              {summary.expert.length === 0 ? (
                <Empty description="当前无专家解析（可能因数据新鲜度不足）" />
              ) : (
                <List
                  itemLayout="vertical"
                  dataSource={summary.expert}
                  renderItem={(item, index) => (
                    <List.Item key={`${item.title}-${index}`}>
                      <Space direction="vertical" size={6} style={{ width: "100%" }}>
                        <Space wrap>
                          <Typography.Text strong>{item.title}</Typography.Text>
                          <Tag color={item.priority === "HIGH" ? "error" : item.priority === "MEDIUM" ? "warning" : "success"}>{item.priority}</Tag>
                        </Space>
                        <Typography.Text>问题：{item.problem}</Typography.Text>
                        <Typography.Text type="secondary">原因：{item.cause}</Typography.Text>
                        <Typography.Text>措施：{item.action}</Typography.Text>
                        <Space direction="vertical" size={2}>
                          <Typography.Text type="secondary">数据证据：</Typography.Text>
                          <Space wrap>
                            {item.dataEvidence.map((evidence, evidenceIndex) => (
                              <Tag key={`${item.title}-data-${evidenceIndex}`}>
                                {evidence.label}：{evidence.value}
                              </Tag>
                            ))}
                          </Space>
                        </Space>
                        <Space direction="vertical" size={2}>
                          <Typography.Text type="secondary">知识依据：</Typography.Text>
                          <Space wrap>
                            {item.knowledgeEvidence.map((evidence) => (
                              <Tag key={`${item.title}-knowledge-${evidence.id}`}>{evidence.title}</Tag>
                            ))}
                          </Space>
                        </Space>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </ProCard>

            <Row gutter={[12, 12]}>
              <Col xs={24} xl={12}>
                <ProCard title="分区风险排行" bordered>
                  {summary.visual.zoneRisks.length === 0 ? (
                    <Empty description="暂无分区风险数据" />
                  ) : (
                    <Table
                      size="small"
                      pagination={false}
                      rowKey={(record) => `${record.zone}-${record.riskScore}`}
                      dataSource={summary.visual.zoneRisks}
                      columns={[
                        { title: "分区", dataIndex: "zone", key: "zone" },
                        { title: "风险分", dataIndex: "riskScore", key: "riskScore" },
                        { title: "异常分钟", dataIndex: "anomalyMinutes", key: "anomalyMinutes" },
                        { title: "异常点", dataIndex: "anomalousSamples", key: "anomalousSamples" },
                      ]}
                    />
                  )}
                </ProCard>
              </Col>
              <Col xs={24} xl={12}>
                <ProCard title="24h 趋势（分指标）" bordered>
                  {summary.visual.trends.length === 0 ? (
                    <Empty description="暂无趋势数据" />
                  ) : (
                    <Table
                      size="small"
                      pagination={{ pageSize: 8, showSizeChanger: false }}
                      rowKey={(record) => `${record.metric}-${record.bucketStartUtc}`}
                      dataSource={summary.visual.trends}
                      columns={[
                        { title: "指标", dataIndex: "metric", key: "metric" },
                        { title: "时间（+08:00）", dataIndex: "bucketStartLocal", key: "bucketStartLocal" },
                        { title: "均值", dataIndex: "avg", key: "avg" },
                        { title: "最小", dataIndex: "min", key: "min" },
                        { title: "最大", dataIndex: "max", key: "max" },
                        { title: "样本数", dataIndex: "count", key: "count" },
                      ]}
                    />
                  )}
                </ProCard>
              </Col>
              <Col xs={24}>
                <ProCard title="异常时间线（按指标）" bordered>
                  {summary.visual.anomalyTimeline.length === 0 ? (
                    <Empty description="暂无异常时间线数据" />
                  ) : (
                    <Table
                      size="small"
                      pagination={false}
                      rowKey={(record) => `${record.metric}-${record.anomalousSamples}`}
                      dataSource={summary.visual.anomalyTimeline}
                      columns={[
                        { title: "指标", dataIndex: "metric", key: "metric" },
                        { title: "异常分钟", dataIndex: "anomalyDurationMinutes", key: "anomalyDurationMinutes" },
                        { title: "异常点数", dataIndex: "anomalousSamples", key: "anomalousSamples" },
                      ]}
                    />
                  )}
                </ProCard>
              </Col>
            </Row>
          </Space>
        )}
      </ProCard>
    </Space>
  );
}
