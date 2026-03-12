"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Checkbox, Col, Empty, Input, InputNumber, List, Row, Space, Spin, Tag, Typography } from "antd";
import { ProCard } from "@ant-design/pro-components";

import {
  confirmCopilotRecommendations,
  fetchCopilotRecommendations,
  generateCopilotRecommendations,
} from "@/src/lib/api/copilot";
import type { CopilotRecommendationItem } from "@/src/types/copilot";

export function CopilotRecommendationsPanel() {
  const [recommendations, setRecommendations] = useState<CopilotRecommendationItem[]>([]);
  const [recommendationTotal, setRecommendationTotal] = useState(0);
  const [recommendationInfo, setRecommendationInfo] = useState<string | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [recommendationLoading, setRecommendationLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [generateHours, setGenerateHours] = useState(24);
  const [generateMaxItems, setGenerateMaxItems] = useState(3);
  const [generateZone, setGenerateZone] = useState("");
  const [generateInstruction, setGenerateInstruction] = useState("");
  const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);

  const pendingRecommendations = useMemo(
    () => recommendations.filter((item) => item.status === "PENDING"),
    [recommendations],
  );

  const loadRecommendations = useCallback(async () => {
    setRecommendationLoading(true);
    try {
      const payload = await fetchCopilotRecommendations({ limit: 20, status: "PENDING" });
      setRecommendations(payload.items);
      setRecommendationTotal(payload.total);
      setSelectedDraftIds((previous) =>
        previous.filter((draftId) => payload.items.some((item) => item.draftId === draftId)),
      );
      setRecommendationError(null);
    } catch (fetchError) {
      setRecommendationError(fetchError instanceof Error ? fetchError.message : "AI 建议草稿加载失败。");
    } finally {
      setRecommendationLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRecommendations();
  }, [loadRecommendations]);

  const onGenerateRecommendations = useCallback(async () => {
    setGenerating(true);
    setRecommendationInfo(null);
    setRecommendationError(null);
    try {
      const payload = await generateCopilotRecommendations({
        hours: generateHours,
        zone: generateZone.trim() || undefined,
        instruction: generateInstruction.trim() || undefined,
        maxItems: generateMaxItems,
      });
      setRecommendationInfo(
        `已生成 ${payload.recommendations.length} 条草稿，来源 ${payload.llmProvider.toUpperCase()}${payload.fallbackUsed ? "（Fallback）" : ""}。`,
      );
      await loadRecommendations();
    } catch (generateError) {
      setRecommendationError(generateError instanceof Error ? generateError.message : "生成 AI 建议草稿失败。");
    } finally {
      setGenerating(false);
    }
  }, [generateHours, generateInstruction, generateMaxItems, generateZone, loadRecommendations]);

  const onConfirmSelected = useCallback(async () => {
    if (selectedDraftIds.length === 0) {
      return;
    }
    setConfirming(true);
    setRecommendationError(null);
    setRecommendationInfo(null);
    try {
      const payload = await confirmCopilotRecommendations({ draftIds: selectedDraftIds });
      setRecommendationInfo(`已确认 ${payload.confirmedCount} 条草稿并写入任务中心。`);
      setSelectedDraftIds([]);
      await loadRecommendations();
    } catch (confirmError) {
      setRecommendationError(confirmError instanceof Error ? confirmError.message : "确认入库失败。");
    } finally {
      setConfirming(false);
    }
  }, [loadRecommendations, selectedDraftIds]);

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {recommendationError ? <Alert type="error" showIcon message="AI建议异常" description={recommendationError} /> : null}
      {recommendationInfo ? <Alert type="success" showIcon message="AI建议处理完成" description={recommendationInfo} /> : null}

      <ProCard title="AI 建议草稿生成（人工确认后入库）" bordered>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Row gutter={[8, 8]}>
            <Col xs={24} md={6}>
              <Typography.Text type="secondary">时间窗口（小时）</Typography.Text>
              <InputNumber
                min={1}
                max={168}
                value={generateHours}
                style={{ width: "100%" }}
                onChange={(value) => setGenerateHours(Number(value || 24))}
              />
            </Col>
            <Col xs={24} md={6}>
              <Typography.Text type="secondary">草稿数量（条）</Typography.Text>
              <InputNumber
                min={1}
                max={10}
                value={generateMaxItems}
                style={{ width: "100%" }}
                onChange={(value) => setGenerateMaxItems(Number(value || 3))}
              />
            </Col>
            <Col xs={24} md={12}>
              <Typography.Text type="secondary">分区（可选）</Typography.Text>
              <Input
                placeholder="例如：1号温室南区"
                value={generateZone}
                onChange={(event) => setGenerateZone(event.target.value)}
              />
            </Col>
            <Col xs={24}>
              <Typography.Text type="secondary">补充指令（可选）</Typography.Text>
              <Input.TextArea
                value={generateInstruction}
                rows={2}
                maxLength={300}
                placeholder="例如：重点关注夜间湿度回落与番茄灰霉风险，给出可执行动作。"
                onChange={(event) => setGenerateInstruction(event.target.value)}
              />
            </Col>
          </Row>

          <Space wrap>
            <Button type="primary" loading={generating} onClick={() => void onGenerateRecommendations()}>
              生成建议草稿
            </Button>
            <Button
              type="default"
              disabled={selectedDraftIds.length === 0}
              loading={confirming}
              onClick={() => void onConfirmSelected()}
            >
              确认并入库任务
            </Button>
            <Button loading={recommendationLoading} onClick={() => void loadRecommendations()}>
              刷新草稿列表
            </Button>
            <Tag color="blue">待确认草稿：{recommendationTotal}</Tag>
          </Space>

          <Spin spinning={recommendationLoading}>
            {pendingRecommendations.length === 0 ? (
              <Empty description="暂无待确认草稿" />
            ) : (
              <List
                itemLayout="vertical"
                dataSource={pendingRecommendations}
                renderItem={(item) => {
                  const checked = selectedDraftIds.includes(item.draftId);
                  return (
                    <List.Item key={item.draftId}>
                      <Space direction="vertical" size={6} style={{ width: "100%" }}>
                        <Space size={[8, 8]} wrap>
                          <Checkbox
                            checked={checked}
                            onChange={(event) => {
                              setSelectedDraftIds((previous) => {
                                if (event.target.checked) {
                                  return Array.from(new Set([...previous, item.draftId]));
                                }
                                return previous.filter((draftId) => draftId !== item.draftId);
                              });
                            }}
                          />
                          <Typography.Text strong>{item.title}</Typography.Text>
                          <Tag color={item.priority === "HIGH" ? "red" : item.priority === "LOW" ? "default" : "orange"}>
                            {item.priority}
                          </Tag>
                          <Tag color="processing">{item.status}</Tag>
                          <Tag>{item.suggestedRole}</Tag>
                          <Tag color={item.fallbackUsed ? "warning" : "success"}>
                            {item.fallbackUsed ? "Fallback" : "DeepSeek"}
                          </Tag>
                        </Space>
                        <Typography.Paragraph style={{ marginBottom: 0 }}>{item.description}</Typography.Paragraph>
                        <Typography.Text type="secondary">原因：{item.reason}</Typography.Text>
                        <Space size={[8, 8]} wrap>
                          <Tag>草稿ID：{item.draftId}</Tag>
                          <Tag>建议时限：{item.dueHours}h</Tag>
                          <Tag>模型：{item.llmModel || "--"}</Tag>
                          <Tag>
                            创建时间：
                            {new Date(item.createdAt).toLocaleString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" })}
                          </Tag>
                        </Space>
                        <Space size={[8, 8]} wrap>
                          {item.dataEvidence.slice(0, 3).map((evidence, index) => (
                            <Tag key={`${item.draftId}-data-${index}`}>
                              {evidence.label}：{evidence.value}
                            </Tag>
                          ))}
                        </Space>
                        <Space size={[8, 8]} wrap>
                          {item.knowledgeEvidence.slice(0, 3).map((evidence) => (
                            <Tag key={`${item.draftId}-knowledge-${evidence.id}`}>{evidence.title}</Tag>
                          ))}
                        </Space>
                      </Space>
                    </List.Item>
                  );
                }}
              />
            )}
          </Spin>
        </Space>
      </ProCard>
    </Space>
  );
}
