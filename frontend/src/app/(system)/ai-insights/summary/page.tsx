"use client";

import { PageContainer } from "@ant-design/pro-components";

import { CopilotSummaryPanel } from "@/src/components/copilot/summary-panel";

export default function AIInsightsSummaryPage() {
  return (
    <PageContainer
      title="AI 智能解析"
      subTitle="基于真实数据输出管理层摘要 + 专家解析，并附证据依据。"
    >
      <CopilotSummaryPanel />
    </PageContainer>
  );
}
