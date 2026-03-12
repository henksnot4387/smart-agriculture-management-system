"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Typography } from "antd";
import { ProCard } from "@ant-design/pro-components";

import type { DashboardRange, MetricKey, MetricSeriesPoint } from "@/src/types/sensor";

type SensorLineChartProps = {
  title: string;
  metric: MetricKey;
  series: MetricSeriesPoint[];
  color: string;
  unit: string;
  range: DashboardRange;
};

const numberFormatters = {
  temperature: new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  humidity: new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 1 }),
  ec: new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  ph: new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
} satisfies Record<MetricKey, Intl.NumberFormat>;

function formatAxisTick(value: string, range: DashboardRange) {
  const date = new Date(value);
  if (range === "24h") {
    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}

function TooltipContent({ active, payload, label, metric, unit }: {
  active?: boolean;
  payload?: Array<{ payload: MetricSeriesPoint }>;
  label?: string;
  metric: MetricKey;
  unit: string;
}) {
  if (!active || !payload?.length || !label) {
    return null;
  }

  const point = payload[0]?.payload;
  const formatter = numberFormatters[metric];

  return (
    <div style={{ background: "rgba(255,255,255,0.96)", border: "1px solid rgba(226,232,240,0.9)", borderRadius: 14, padding: 14, boxShadow: "0 14px 40px -28px rgba(15, 118, 110, 0.5)" }}>
      <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
        {new Date(label).toLocaleString("zh-CN", {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })}
      </Typography.Text>
      <Typography.Text style={{ display: "block" }}>平均值：{formatter.format(point.avg)} {unit}</Typography.Text>
      <Typography.Text style={{ display: "block" }}>最小 / 最大：{formatter.format(point.min)} / {formatter.format(point.max)} {unit}</Typography.Text>
      <Typography.Text style={{ display: "block" }}>样本数：{point.count}</Typography.Text>
    </div>
  );
}

export function SensorLineChart({ title, metric, series, color, unit, range }: SensorLineChartProps) {
  const formatter = numberFormatters[metric];

  return (
    <ProCard bordered title={title} extra={<Typography.Text type="secondary">单位：{unit}</Typography.Text>}>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`chart-fill-${metric}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.28} />
                <stop offset="95%" stopColor={color} stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(148,163,184,0.18)" vertical={false} />
            <XAxis
              dataKey="bucketStartLocal"
              tickFormatter={(value) => formatAxisTick(value, range)}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
              stroke="#64748b"
              fontSize={12}
            />
            <YAxis
              tickFormatter={(value: number) => formatter.format(value)}
              tickLine={false}
              axisLine={false}
              width={56}
              stroke="#64748b"
              fontSize={12}
            />
            <Tooltip content={<TooltipContent metric={metric} unit={unit} />} />
            <Area type="monotone" dataKey="avg" stroke={color} fill={`url(#chart-fill-${metric})`} strokeWidth={3} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </ProCard>
  );
}
