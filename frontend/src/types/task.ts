export type TaskStatus = "PENDING" | "APPROVED" | "IN_PROGRESS" | "COMPLETED";
export type TaskPriority = "LOW" | "MEDIUM" | "HIGH";
export type TaskSource = "AI" | "MANUAL" | "EXTERNAL";
export type AssignedToFilter = "me" | "unassigned" | "all";

export type TaskItem = {
  taskId: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  source: TaskSource;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  approvedAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  dueAt?: string | null;
  createdById: string;
  createdByEmail?: string | null;
  assigneeId?: string | null;
  assigneeEmail?: string | null;
  approvedById?: string | null;
  approvedByEmail?: string | null;
};

export type TaskListPayload = {
  total: number;
  limit: number;
  items: TaskItem[];
};

export type TaskDetailPayload = {
  task: TaskItem;
};

export type TaskTransitionPayload = {
  message: string;
  task: TaskItem;
};

export type TaskAssigneeOption = {
  id: string;
  email: string;
  name?: string | null;
  role: string;
};

export type TaskAssigneeListPayload = {
  items: TaskAssigneeOption[];
};

export type ApproveTaskRequest = {
  assigneeId?: string | null;
};

export type OperationType =
  | "IRRIGATION"
  | "FERTIGATION"
  | "PLANT_PROTECTION"
  | "CLIMATE_ADJUSTMENT"
  | "INSPECTION"
  | "OTHER";

export type SensorReading = {
  temperature?: number | null;
  humidity?: number | null;
  ec?: number | null;
  ph?: number | null;
};

export type ExecutionMaterial = {
  name: string;
  amount: number;
  unit: string;
};

export type CompleteTaskRequest = {
  operationType: OperationType;
  executedActions: string[];
  readingsBefore?: SensorReading | null;
  readingsAfter?: SensorReading | null;
  materials?: ExecutionMaterial[];
  anomalies?: string[];
  resultSummary: string;
  attachments?: string[];
};
