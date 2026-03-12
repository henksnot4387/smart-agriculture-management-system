export type VisionTaskStatus = "PROCESSING" | "DONE" | "FAILED";

export type VisionDetectionBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type VisionDetectionItem = {
  label: string;
  confidence: number;
  bbox?: VisionDetectionBox | null;
};

export type VisionTask = {
  taskId: string;
  status: VisionTaskStatus;
  source: string;
  imageUrl: string;
  diseaseType?: string | null;
  confidence?: number | null;
  detections: VisionDetectionItem[];
  engine?: string | null;
  device?: string | null;
  fallbackOccurred?: boolean | null;
  error?: string | null;
  queuedAt?: string | null;
  processedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type VisionTaskListPayload = {
  items: VisionTask[];
};

export type VisionRuntimePayload = {
  mode: string;
  engine: string;
  preferredDevice: string;
  activeDevice: string;
  fallbackOccurred: boolean;
  storageBackend: string;
  queueKey: string;
  queueDepth: number;
  maxUploadMb: number;
};

export type VisionWsUrlPayload = {
  url: string;
};

export type VisionTaskEventPayload = {
  type: "vision.connected" | "vision.pong" | "vision.task.accepted" | "vision.task.updated";
  task?: VisionTask;
  queueDepth?: number;
  connectedAt?: string;
  runtime?: VisionRuntimePayload;
  at?: string;
};
