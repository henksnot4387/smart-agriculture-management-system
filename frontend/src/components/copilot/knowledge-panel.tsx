"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Col, Empty, Input, Row, Select, Space, Tag, Typography } from "antd";
import { ProCard } from "@ant-design/pro-components";

import { fetchKnowledgeItems, fetchKnowledgeMeta } from "@/src/lib/api/copilot";
import type { KnowledgeItem, KnowledgeMetaPayload } from "@/src/types/copilot";

export function CopilotKnowledgePanel() {
  const [knowledgeMeta, setKnowledgeMeta] = useState<KnowledgeMetaPayload | null>(null);
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [knowledgeTotal, setKnowledgeTotal] = useState(0);
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [query, setQuery] = useState("");
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadKnowledge = useCallback(
    async (options?: { category?: string; query?: string; keywords?: string[] }) => {
      setLoading(true);
      try {
        const [metaPayload, listPayload] = await Promise.all([
          fetchKnowledgeMeta(),
          fetchKnowledgeItems({
            category: options?.category,
            q: options?.query,
            keywords: options?.keywords,
            limit: 60,
          }),
        ]);
        setKnowledgeMeta(metaPayload);
        setKnowledgeItems(listPayload.items);
        setKnowledgeTotal(listPayload.total);
        setError(null);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "知识库数据加载失败。");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadKnowledge();
  }, [loadKnowledge]);

  const categoryOptions = useMemo(
    () =>
      (knowledgeMeta?.categories || []).map((item) => ({
        label: item.name,
        value: item.id,
      })),
    [knowledgeMeta],
  );

  const onSearch = useCallback(async () => {
    await loadKnowledge({
      category,
      query: query.trim() || undefined,
      keywords: selectedKeywords,
    });
  }, [category, loadKnowledge, query, selectedKeywords]);

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {error ? <Alert type="warning" showIcon message="知识库加载失败" description={error} /> : null}

      <ProCard title="本地知识库（分类 + 关键词）" bordered loading={loading}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Row gutter={[8, 8]}>
            <Col xs={24} md={8}>
              <Select
                allowClear
                style={{ width: "100%" }}
                placeholder="按分类筛选"
                options={categoryOptions}
                value={category}
                onChange={(value) => setCategory(value)}
              />
            </Col>
            <Col xs={24} md={10}>
              <Input
                placeholder="输入关键词，如：番茄 脐腐 水肥"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onPressEnter={() => void onSearch()}
              />
            </Col>
            <Col xs={24} md={6}>
              <Select
                mode="multiple"
                allowClear
                style={{ width: "100%" }}
                placeholder="高频关键词"
                value={selectedKeywords}
                options={(knowledgeMeta?.topKeywords || []).slice(0, 30).map((keyword) => ({
                  label: keyword,
                  value: keyword,
                }))}
                onChange={(values) => setSelectedKeywords(values)}
              />
            </Col>
          </Row>

          <Space>
            <Tag color="blue">知识条目：{knowledgeTotal}</Tag>
            <Tag>版本：{knowledgeMeta?.version || "--"}</Tag>
            <Tag>采集关键词：{knowledgeMeta?.seedKeywords.length || 0}</Tag>
            <Tag color={knowledgeMeta && knowledgeMeta.harvestSuccessRate >= 70 ? "success" : "warning"}>
              采集成功率：{knowledgeMeta ? `${knowledgeMeta.harvestSuccessRate.toFixed(1)}%` : "--"}
            </Tag>
            <Tag>
              最近采集：
              {knowledgeMeta?.harvestLastRunAt
                ? new Date(knowledgeMeta.harvestLastRunAt).toLocaleString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" })
                : "--"}
            </Tag>
            <Button type="link" size="small" onClick={() => void onSearch()}>
              应用筛选
            </Button>
            <Button
              type="link"
              size="small"
              onClick={() => {
                setCategory(undefined);
                setQuery("");
                setSelectedKeywords([]);
                void loadKnowledge();
              }}
            >
              重置
            </Button>
          </Space>

          {knowledgeItems.length === 0 ? (
            <Empty description="没有匹配到知识条目" />
          ) : (
            <Row gutter={[12, 12]}>
              {knowledgeItems.map((item) => (
                <Col xs={24} key={item.id}>
                  <ProCard bordered title={item.title} subTitle={item.categoryName}>
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Typography.Paragraph style={{ marginBottom: 0 }}>{item.summary}</Typography.Paragraph>
                      {item.whyImportant ? (
                        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                          为什么重要：{item.whyImportant}
                        </Typography.Paragraph>
                      ) : null}
                      <Space size={[8, 8]} wrap>
                        {item.keywords.map((keyword) => (
                          <Tag key={`${item.id}-${keyword}`}>{keyword}</Tag>
                        ))}
                      </Space>
                      <Typography.Text type="secondary">
                        来源：{item.source.publisher || "未知"} ·{" "}
                        <a href={item.source.url} target="_blank" rel="noreferrer">
                          {item.source.title}
                        </a>
                      </Typography.Text>
                      <Space size={[8, 8]} wrap>
                        <Tag color={item.fetchStatus === "success" ? "success" : item.fetchStatus === "failed" ? "error" : "default"}>
                          采集状态：{item.fetchStatus || "--"}
                        </Tag>
                        <Tag>
                          最近尝试：
                          {item.lastAttemptAt
                            ? new Date(item.lastAttemptAt).toLocaleString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" })
                            : "--"}
                        </Tag>
                        {item.lastError ? <Tag color="error">错误：{item.lastError}</Tag> : null}
                      </Space>
                      {item.actionablePoints.length > 0 ? (
                        <div>
                          <Typography.Text strong>落地建议：</Typography.Text>
                          <ul style={{ margin: "8px 0 0 20px", padding: 0 }}>
                            {item.actionablePoints.map((point) => (
                              <li key={`${item.id}-${point}`}>
                                <Typography.Text>{point}</Typography.Text>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </Space>
                  </ProCard>
                </Col>
              ))}
            </Row>
          )}
        </Space>
      </ProCard>
    </Space>
  );
}

