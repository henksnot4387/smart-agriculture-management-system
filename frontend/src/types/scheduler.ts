export type SchedulerJob = {
  jobId: string;
  taskName: string;
  name: string;
  description: string;
  scheduleType: string;
  scheduleValue: string;
  isPaused: boolean;
  lastStatus?: string | null;
  lastMessage?: string | null;
  lastError?: string | null;
  lastRunStartedAt?: string | null;
  lastRunFinishedAt?: string | null;
  lastDurationMs?: number | null;
  nextRunAt?: string | null;
};

export type SchedulerRun = {
  id: number;
  jobId: string;
  trigger: string;
  status: string;
  message?: string | null;
  error?: string | null;
  startedAt: string;
  finishedAt?: string | null;
  durationMs?: number | null;
};

export type SchedulerJobsPayload = {
  jobs: SchedulerJob[];
};

export type SchedulerRunsPayload = {
  runs: SchedulerRun[];
};

export type SchedulerDispatchPayload = {
  jobId: string;
  taskId?: string | null;
  dispatchedAt: string;
};

export type SchedulerHealthPayload = {
  brokerOk: boolean;
  brokerError?: string | null;
  totalJobs: number;
  pausedJobs: number;
  latestFinishedAt?: string | null;
  timestamp: string;
};
