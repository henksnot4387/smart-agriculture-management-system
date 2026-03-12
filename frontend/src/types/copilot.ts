export type CopilotMetricKey = "temperature" | "humidity" | "ec" | "ph";
export type AIInsightFreshnessStatus = "FRESH" | "WARNING" | "STALE";

export type AIInsightDataEvidence = {
  label: string;
  value: string;
};

export type AIInsightKnowledgeEvidence = {
  id: string;
  title: string;
  summary: string;
  sourceUrl?: string | null;
};

export type AIInsightExecutive = {
  headline: string;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
  keyFindings: string[];
};

export type AIInsightExpertItem = {
  title: string;
  problem: string;
  cause: string;
  action: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  dataEvidence: AIInsightDataEvidence[];
  knowledgeEvidence: AIInsightKnowledgeEvidence[];
};

export type AIInsightZoneRiskItem = {
  zone: string;
  riskScore: number;
  anomalyMinutes: number;
  anomalousSamples: number;
};

export type AIInsightTrendPoint = {
  metric: CopilotMetricKey;
  bucketStartUtc: string;
  bucketStartLocal: string;
  avg: number;
  min: number;
  max: number;
  count: number;
};

export type AIInsightAnomalyTimelineItem = {
  metric: CopilotMetricKey;
  anomalyDurationMinutes: number;
  anomalousSamples: number;
};

export type AIInsightVisual = {
  zoneRisks: AIInsightZoneRiskItem[];
  trends: AIInsightTrendPoint[];
  anomalyTimeline: AIInsightAnomalyTimelineItem[];
};

export type CopilotRecommendationPriority = "LOW" | "MEDIUM" | "HIGH";
export type CopilotSuggestedRole = "SUPER_ADMIN" | "ADMIN" | "EXPERT" | "WORKER";
export type CopilotRecommendationDraftStatus = "PENDING" | "CONFIRMED";
export type CopilotRecommendationTaskStatus = "PENDING" | "APPROVED" | "IN_PROGRESS" | "COMPLETED";

export type CopilotRecommendationItem = {
  draftId: string;
  title: string;
  description: string;
  reason: string;
  priority: CopilotRecommendationPriority;
  suggestedRole: CopilotSuggestedRole;
  dueHours: number;
  status: CopilotRecommendationDraftStatus;
  llmProvider: string;
  llmModel?: string | null;
  fallbackUsed: boolean;
  knowledgeRefs: string[];
  dataEvidence: AIInsightDataEvidence[];
  knowledgeEvidence: AIInsightKnowledgeEvidence[];
  createdAt: string;
  confirmedAt?: string | null;
  taskId?: string | null;
};

export type AIInsightMeta = {
  source: string;
  freshnessStatus: AIInsightFreshnessStatus;
  pageRefreshedAt: string;
  latestSampleAtUtc?: string | null;
  latestSampleAtLocal?: string | null;
  timezone: string;
  storageTimezone: string;
  engineProvider: string;
  engineModel?: string | null;
  fallbackUsed: boolean;
  warningMessage?: string | null;
};

export type AIInsightSummaryPayload = {
  meta: AIInsightMeta;
  executive: AIInsightExecutive;
  expert: AIInsightExpertItem[];
  visual: AIInsightVisual;
  recommendationDrafts: CopilotRecommendationItem[];
};

export type CopilotSummaryPayload = AIInsightSummaryPayload;

export type KnowledgeCategory = {
  id: string;
  name: string;
  description: string;
};

export type KnowledgeSource = {
  title: string;
  url: string;
  type?: string | null;
  publisher?: string | null;
  publishedAt?: string | null;
  fetchedAt?: string | null;
};

export type KnowledgeItem = {
  id: string;
  categoryId: string;
  categoryName: string;
  title: string;
  summary: string;
  whyImportant?: string | null;
  actionablePoints: string[];
  keywords: string[];
  source: KnowledgeSource;
  lastAttemptAt?: string | null;
  fetchStatus?: string | null;
  lastError?: string | null;
  updatedAt?: string | null;
};

export type KnowledgeListPayload = {
  total: number;
  items: KnowledgeItem[];
};

export type KnowledgeMetaPayload = {
  version: string;
  generatedAt: string;
  seedKeywords: string[];
  categories: KnowledgeCategory[];
  topKeywords: string[];
  harvestLastRunAt?: string | null;
  harvestAttempted: number;
  harvestSucceeded: number;
  harvestFailed: number;
  harvestSuccessRate: number;
};

export type CopilotRecommendationGenerateRequest = {
  hours?: number;
  zone?: string;
  provider?: string;
  instruction?: string;
  maxItems?: number;
};

export type CopilotRecommendationGeneratePayload = {
  generatedAtUtc: string;
  hours: number;
  zone?: string | null;
  provider?: string | null;
  llmProvider: string;
  llmModel?: string | null;
  fallbackUsed: boolean;
  recommendations: CopilotRecommendationItem[];
};

export type CopilotRecommendationListPayload = {
  total: number;
  limit: number;
  status?: CopilotRecommendationDraftStatus | null;
  items: CopilotRecommendationItem[];
};

export type CopilotRecommendationConfirmRequest = {
  draftIds: string[];
};

export type CopilotRecommendationConfirmPayload = {
  confirmedAtUtc: string;
  confirmedCount: number;
  tasks: Array<{
    draftId: string;
    taskId: string;
    title: string;
    status: CopilotRecommendationTaskStatus;
    priority: CopilotRecommendationPriority;
    createdAt: string;
  }>;
};
