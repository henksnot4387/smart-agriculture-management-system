"use client";

import { Button, Result } from "antd";
import Link from "next/link";

import { PageContainer, ProCard } from "@ant-design/pro-components";

type ModulePlaceholderProps = {
  title: string;
  subtitle: string;
  relatedTasks: string[];
};

export function ModulePlaceholder({ title, subtitle, relatedTasks }: ModulePlaceholderProps) {
  return (
    <PageContainer title={title} subTitle={subtitle}>
      <ProCard>
        <Result
          status="info"
          title={`${title}模块正在建设中`}
          subTitle={`该页面将承接 ${relatedTasks.join(" / ")} 相关业务能力，当前阶段先完成系统壳子与导航结构。`}
          extra={
            <Button type="primary">
              <Link href="/dashboard">返回数据总览</Link>
            </Button>
          }
        />
      </ProCard>
    </PageContainer>
  );
}
