"use client";

import { PageContainer } from "@ant-design/pro-components";

import { CopilotKnowledgePanel } from "@/src/components/copilot/knowledge-panel";

export default function AIInsightsKnowledgePage() {
  return (
    <PageContainer
      title="本地知识库（分类 + 关键词）"
      subTitle="按分类与关键词检索知识条目，查看来源与采集健康状态。"
    >
      <CopilotKnowledgePanel />
    </PageContainer>
  );
}
