import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Progress, Tag, Typography } from "antd";
import { ProCard } from "@ant-design/pro-components";

import type { MetricKey, MetricSummary } from "@/src/types/sensor";

type MetricCardProps = {
  metric: MetricKey;
  summary?: MetricSummary;
};

type MetricMeta = {
  label: string;
  unit: string;
  color: string;
  precision: number;
};

const metricMeta: Record<MetricKey, MetricMeta> = {
  temperature: { label: "平均温度", unit: "°C", color: "#ea580c", precision: 1 },
  humidity: { label: "平均湿度", unit: "%", color: "#0f766e", precision: 1 },
  ec: { label: "平均EC", unit: "mS/cm", color: "#65a30d", precision: 2 },
  ph: { label: "平均pH", unit: "pH", color: "#0369a1", precision: 2 },
};

function formatTimestamp(value?: string) {
  if (!value) {
    return "暂无";
  }

  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function calculateRangePosition(summary?: MetricSummary) {
  if (!summary) {
    return 0;
  }
  if (summary.max === summary.min) {
    return 100;
  }

  const rawPercent = ((summary.latest - summary.min) / (summary.max - summary.min)) * 100;
  return Math.max(0, Math.min(100, rawPercent));
}

export function MetricCard({ metric, summary }: MetricCardProps) {
  const meta = metricMeta[metric];
  const latestText = summary ? `${summary.latest.toFixed(meta.precision)} ${meta.unit}` : "--";
  const rangePosition = calculateRangePosition(summary);

  return (
    <ProCard bordered hoverable style={{ height: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {meta.label}
          </Typography.Text>
          <div
            style={{
              marginTop: 4,
              color: meta.color,
              fontWeight: 700,
              fontSize: 28,
              lineHeight: 1.05,
              whiteSpace: "nowrap",
              letterSpacing: "-0.02em",
            }}
          >
            {latestText}
          </div>
        </div>
        <Tag color="processing">{summary ? "已同步" : "暂无数据"}</Tag>
      </div>

      <Typography.Paragraph type="secondary" style={{ marginTop: 6, marginBottom: 12, fontSize: 13 }}>
        最近更新时间：{formatTimestamp(summary?.latestAtLocal)}
      </Typography.Paragraph>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            平均值
          </Typography.Text>
          <div style={{ marginTop: 4, fontWeight: 600, fontSize: 15 }}>
            {summary ? `${summary.avg.toFixed(meta.precision)} ${meta.unit}` : "--"}
          </div>
        </div>
        <div>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            样本数
          </Typography.Text>
          <div style={{ marginTop: 4, fontWeight: 600, fontSize: 15 }}>{summary?.sampleCount ?? "--"}</div>
        </div>
      </div>

      <div style={{ marginTop: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}><ArrowDownOutlined /> 最小值</Typography.Text>
          <Typography.Text style={{ fontSize: 13 }}>{summary ? `${summary.min.toFixed(meta.precision)} ${meta.unit}` : "--"}</Typography.Text>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}><ArrowUpOutlined /> 最大值</Typography.Text>
          <Typography.Text style={{ fontSize: 13 }}>{summary ? `${summary.max.toFixed(meta.precision)} ${meta.unit}` : "--"}</Typography.Text>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            区间位置（当前值相对最小-最大）
          </Typography.Text>
          <Typography.Text style={{ fontSize: 12, color: meta.color }}>
            {summary ? `${rangePosition.toFixed(0)}%` : "--"}
          </Typography.Text>
        </div>
        <Progress
          percent={rangePosition}
          showInfo={false}
          size={["100%", 6]}
          strokeColor={meta.color}
          trailColor="rgba(148, 163, 184, 0.16)"
        />
      </div>
    </ProCard>
  );
}
