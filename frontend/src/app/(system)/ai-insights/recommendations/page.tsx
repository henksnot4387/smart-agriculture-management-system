"use client";

import { PageContainer } from "@ant-design/pro-components";

import { CopilotRecommendationsPanel } from "@/src/components/copilot/recommendations-panel";

export default function AIInsightsRecommendationsPage() {
  return (
    <PageContainer
      title="AI 建议草稿与任务入库"
      subTitle="先生成草稿，再人工确认写入任务中心（默认 PENDING）。"
    >
      <CopilotRecommendationsPanel />
    </PageContainer>
  );
}
