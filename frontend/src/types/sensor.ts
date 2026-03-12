export type DashboardRange = "24h" | "7d";
export type MetricKey = "temperature" | "humidity" | "ec" | "ph";

export type MetricSummary = {
  latest: number;
  latestAtUtc: string;
  latestAtLocal: string;
  avg: number;
  min: number;
  max: number;
  sampleCount: number;
};

export type MetricSeriesPoint = {
  bucketStartUtc: string;
  bucketStartLocal: string;
  avg: number;
  min: number;
  max: number;
  count: number;
};

export type MetricSummaryGroup = Partial<Record<MetricKey, MetricSummary>>;
export type MetricSeriesGroup = Record<MetricKey, MetricSeriesPoint[]>;

export type SensorDashboardPayload = {
  summary: MetricSummaryGroup;
  series: MetricSeriesGroup;
  meta: {
    range: DashboardRange;
    bucket: string;
    zone?: string | null;
    provider?: string | null;
    timezone: string;
    storageTimezone: string;
  };
};

export type GreenhouseOverviewItem = {
  zone: string;
  displayName: string;
  group: string;
  area: string;
  category: "greenhouse" | "fertigation";
  latestAtLocal: string | null;
  metrics: Partial<Record<MetricKey, number>>;
  status: "正常" | "部分采集" | "数据缺失";
};

export type DashboardHomePayload = {
  dashboard: SensorDashboardPayload;
  zones: GreenhouseOverviewItem[];
};
