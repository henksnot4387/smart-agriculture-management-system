export type OpsCatalogItem = {
  controlTypeId: string;
  parameterId: string;
  controlTypeName: string;
  parameterName: string;
  metricKey: string;
  displayName: string;
  module: string;
  moduleLabel: string;
  area: string;
  valueType: string;
  unit: string;
  canonicalMetric?: string | null;
  covered: boolean;
  latestSampleAtUtc?: string | null;
  latestSampleAtLocal?: string | null;
};

export type OpsCatalogPayload = {
  version: string;
  source: string;
  systemId: string;
  provider: string;
  coverage: {
    total: number;
    covered: number;
    coverageRate: number;
    gatePassed: boolean;
  };
  items: OpsCatalogItem[];
};

export type OpsMetricValue = {
  metricKey: string;
  displayName: string;
  value: number;
  unit: string;
  valueType: string;
  module: string;
  moduleLabel: string;
  area: string;
  recordedAtUtc: string;
  recordedAtLocal: string;
};

export type OpsZoneSnapshot = {
  zone: string;
  latestSampleAtUtc?: string | null;
  latestSampleAtLocal?: string | null;
  metrics: OpsMetricValue[];
};

export type OpsModuleSnapshot = {
  module: string;
  moduleLabel: string;
  zoneCount: number;
  metricCount: number;
};

export type OpsLivePayload = {
  meta: {
    provider: string;
    lookbackHours: number;
    pageRefreshedAt: string;
    latestSampleAtUtc?: string | null;
    latestSampleAtLocal?: string | null;
    freshnessStatus: "FRESH" | "WARNING" | "STALE";
    warningMessage?: string | null;
    timezone: string;
    storageTimezone: string;
  };
  zones: OpsZoneSnapshot[];
  modules: OpsModuleSnapshot[];
};

export type OpsTrendPoint = {
  metricKey: string;
  displayName: string;
  module: string;
  moduleLabel: string;
  bucketStartUtc: string;
  bucketStartLocal: string;
  avg: number;
  min: number;
  max: number;
  count: number;
};

export type OpsTrendsPayload = {
  provider: string;
  startUtc: string;
  endUtc: string;
  zone?: string | null;
  points: OpsTrendPoint[];
};
