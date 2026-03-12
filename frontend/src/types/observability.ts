export type ObservabilityRouteMetric = {
  route: string;
  requestCount: number;
  errorCount: number;
  slowCount: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
  maxLatencyMs: number;
};

export type ObservabilityDomainMetric = {
  domain: string;
  requestCount: number;
  errorCount: number;
  slowCount: number;
};

export type ObservabilityErrorCodeMetric = {
  errorCode: string;
  count: number;
};

export type ObservabilityErrorEvent = {
  requestId: string;
  method: string;
  path: string;
  route: string;
  statusCode: number;
  durationMs: number;
  errorCode?: string | null;
  userId?: string | null;
  userRole?: string | null;
  occurredAt: string;
};

export type ObservabilityTaskFailureMetric = {
  jobId: string;
  failedCount: number;
  lastFailedAt?: string | null;
  lastError?: string | null;
};

export type ObservabilityOverviewPayload = {
  windowHours: number;
  slowThresholdMs: number;
  totalRequests: number;
  errorRequests: number;
  slowRequests: number;
  p95LatencyMs: number;
  topRoutes: ObservabilityRouteMetric[];
  domainStats: ObservabilityDomainMetric[];
  errorCodeStats: ObservabilityErrorCodeMetric[];
  taskFailures: ObservabilityTaskFailureMetric[];
};

export type ObservabilityErrorsPayload = {
  windowHours: number;
  items: ObservabilityErrorEvent[];
};

export type ObservabilitySlowRequestsPayload = {
  windowHours: number;
  slowThresholdMs: number;
  items: ObservabilityErrorEvent[];
};

export type ObservabilityTaskFailuresPayload = {
  windowHours: number;
  items: ObservabilityTaskFailureMetric[];
};
