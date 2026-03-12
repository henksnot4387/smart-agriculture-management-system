"use client";

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Divider, Space, Tag, Typography } from "antd";
import { ProCard } from "@ant-design/pro-components";

import { RangeToggle } from "@/src/components/dashboard/range-toggle";
import type { DashboardRange } from "@/src/types/sensor";

type DashboardHeaderProps = {
  range: DashboardRange;
  isRefreshing: boolean;
  lastUpdated: string | null;
  latestSampleAtLocal: string | null;
  onRefresh: () => void;
  onRangeChange: (range: DashboardRange) => void;
};

function formatDisplayTimestamp(value: string | null, emptyText = "等待首次同步") {
  if (!value) {
    return emptyText;
  }

  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}

export function DashboardHeader({
  range,
  isRefreshing,
  lastUpdated,
  latestSampleAtLocal,
  onRefresh,
  onRangeChange,
}: DashboardHeaderProps) {
  return (
    <ProCard bordered style={{ height: "100%" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, height: "100%" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ maxWidth: 640 }}>
            <Space size={8} wrap>
              <Typography.Text type="secondary">系统首页</Typography.Text>
              <Tag color={isRefreshing ? "processing" : "default"}>{isRefreshing ? "刷新中" : "稳定"}</Tag>
            </Space>
            <Typography.Title level={2} style={{ marginTop: 8, marginBottom: 8, fontSize: 28, lineHeight: 1.2 }}>
              智慧农业管理系统总览
            </Typography.Title>
            
          </div>

          <Space size={12} wrap align="center">
            <RangeToggle value={range} onChange={onRangeChange} disabled={isRefreshing} />
            <Button icon={<ReloadOutlined />} onClick={onRefresh} loading={isRefreshing}>
              立即刷新
            </Button>
          </Space>
        </div>

        <Divider style={{ marginBlock: 0 }} />

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              页面刷新时间
            </Typography.Text>
            <div style={{ marginTop: 6, fontWeight: 600, fontSize: 15 }}>{formatDisplayTimestamp(lastUpdated)}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              数据最新采样时间（+08:00）
            </Typography.Text>
            <div style={{ marginTop: 6, fontWeight: 600, fontSize: 15 }}>{formatDisplayTimestamp(latestSampleAtLocal, "暂无采样")}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              当前范围
            </Typography.Text>
            <div style={{ marginTop: 6, fontWeight: 600, fontSize: 15 }}>{range === "24h" ? "近24小时" : "近7天"}</div>
          </div>
          <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              刷新策略
            </Typography.Text>
            <div style={{ marginTop: 6, fontWeight: 600, fontSize: 15 }}>首屏加载 + 30秒轮询</div>
          </div>
        </div>
      </div>
    </ProCard>
  );
}
