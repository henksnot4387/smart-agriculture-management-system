"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import {
  fetchSchedulerHealth,
  fetchSchedulerJobs,
  fetchSchedulerRuns,
  pauseSchedulerJob,
  resumeSchedulerJob,
  runSchedulerJob,
  SchedulerApiError,
} from "@/src/lib/api/scheduler";
import type { SchedulerHealthPayload, SchedulerJob, SchedulerRun } from "@/src/types/scheduler";

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function renderStatus(status?: string | null) {
  const normalized = String(status || "UNKNOWN").toUpperCase();
  if (normalized === "SUCCESS") return <Tag color="success">SUCCESS</Tag>;
  if (normalized === "FAILED") return <Tag color="error">FAILED</Tag>;
  if (normalized === "RUNNING") return <Tag color="processing">RUNNING</Tag>;
  if (normalized === "SKIPPED") return <Tag color="warning">SKIPPED</Tag>;
  return <Tag>{normalized}</Tag>;
}

export function SchedulerConsole() {
  const [jobs, setJobs] = useState<SchedulerJob[]>([]);
  const [runs, setRuns] = useState<SchedulerRun[]>([]);
  const [health, setHealth] = useState<SchedulerHealthPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mutatingJobId, setMutatingJobId] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsPayload, runsPayload, healthPayload] = await Promise.all([
        fetchSchedulerJobs(),
        fetchSchedulerRuns(120),
        fetchSchedulerHealth(),
      ]);
      setJobs(jobsPayload.jobs);
      setRuns(runsPayload.runs);
      setHealth(healthPayload);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "调度中心加载失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const triggerAction = useCallback(
    async (jobId: string, action: "run" | "pause" | "resume") => {
      setMutatingJobId(jobId);
      try {
        if (action === "run") {
          await runSchedulerJob(jobId);
        } else if (action === "pause") {
          await pauseSchedulerJob(jobId);
        } else {
          await resumeSchedulerJob(jobId);
        }
        await loadAll();
      } catch (actionError) {
        if (actionError instanceof SchedulerApiError) {
          setError(actionError.message);
        } else if (actionError instanceof Error) {
          setError(actionError.message);
        } else {
          setError("任务操作失败。");
        }
      } finally {
        setMutatingJobId(null);
      }
    },
    [loadAll],
  );

  const jobColumns = useMemo<ColumnsType<SchedulerJob>>(
    () => [
      {
        title: "任务",
        dataIndex: "name",
        key: "name",
        width: 220,
        render: (_: unknown, row) => (
          <Space direction="vertical" size={2}>
            <Typography.Text strong>{row.name}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {row.description}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: "调度",
        key: "schedule",
        width: 180,
        render: (_: unknown, row) => (
          <Space direction="vertical" size={2}>
            <Tag color="blue">{row.scheduleType.toUpperCase()}</Tag>
            <Typography.Text>{row.scheduleValue}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "状态",
        key: "status",
        width: 140,
        render: (_: unknown, row) => (
          <Space direction="vertical" size={2}>
            {row.isPaused ? <Tag color="default">PAUSED</Tag> : <Tag color="success">ACTIVE</Tag>}
            {renderStatus(row.lastStatus)}
          </Space>
        ),
      },
      {
        title: "最近执行",
        key: "lastRun",
        width: 220,
        render: (_: unknown, row) => (
          <Space direction="vertical" size={2}>
            <Typography.Text type="secondary">开始：{formatDateTime(row.lastRunStartedAt)}</Typography.Text>
            <Typography.Text type="secondary">完成：{formatDateTime(row.lastRunFinishedAt)}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "下次执行",
        dataIndex: "nextRunAt",
        key: "nextRunAt",
        width: 180,
        render: (value: string | null | undefined) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 220,
        render: (_: unknown, row) => (
          <Space>
            <Button
              size="small"
              loading={mutatingJobId === row.jobId}
              onClick={() => void triggerAction(row.jobId, "run")}
            >
              立即执行
            </Button>
            {row.isPaused ? (
              <Button
                size="small"
                type="primary"
                ghost
                loading={mutatingJobId === row.jobId}
                onClick={() => void triggerAction(row.jobId, "resume")}
              >
                恢复
              </Button>
            ) : (
              <Button
                size="small"
                danger
                ghost
                loading={mutatingJobId === row.jobId}
                onClick={() => void triggerAction(row.jobId, "pause")}
              >
                暂停
              </Button>
            )}
          </Space>
        ),
      },
    ],
    [mutatingJobId, triggerAction],
  );

  const runColumns = useMemo<ColumnsType<SchedulerRun>>(
    () => [
      {
        title: "任务ID",
        dataIndex: "jobId",
        key: "jobId",
        width: 210,
        render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
      },
      {
        title: "触发方式",
        dataIndex: "trigger",
        key: "trigger",
        width: 100,
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "执行状态",
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value: string) => renderStatus(value),
      },
      {
        title: "开始时间",
        dataIndex: "startedAt",
        key: "startedAt",
        width: 180,
        render: (value: string) => formatDateTime(value),
      },
      {
        title: "结束时间",
        dataIndex: "finishedAt",
        key: "finishedAt",
        width: 180,
        render: (value: string | null | undefined) => formatDateTime(value),
      },
      {
        title: "耗时",
        dataIndex: "durationMs",
        key: "durationMs",
        width: 100,
        render: (value: number | null | undefined) => (typeof value === "number" ? `${value} ms` : "--"),
      },
      {
        title: "说明",
        dataIndex: "message",
        key: "message",
        ellipsis: true,
      },
      {
        title: "错误",
        dataIndex: "error",
        key: "error",
        ellipsis: true,
      },
    ],
    [],
  );

  return (
    <PageContainer
      title="调度中心"
      subTitle="仅超级管理员可用：统一管理数据同步、知识采集、摘要预计算和任务清理。"
      extra={[
        <Button key="refresh" onClick={() => void loadAll()} loading={loading}>
          刷新
        </Button>,
      ]}
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {error ? <Alert type="warning" showIcon message="操作失败" description={error} /> : null}

        <ProCard title="调度健康状态" bordered>
          <Space size={[12, 12]} wrap>
            <Tag color={health?.brokerOk ? "success" : "error"}>{health?.brokerOk ? "Broker 正常" : "Broker 异常"}</Tag>
            <Tag>任务总数：{health?.totalJobs ?? "--"}</Tag>
            <Tag>暂停任务：{health?.pausedJobs ?? "--"}</Tag>
            <Tag>最近完成：{formatDateTime(health?.latestFinishedAt)}</Tag>
          </Space>
          {health?.brokerError ? (
            <Typography.Paragraph type="danger" style={{ marginTop: 8, marginBottom: 0 }}>
              Broker 错误：{health.brokerError}
            </Typography.Paragraph>
          ) : null}
        </ProCard>

        <ProCard title="任务清单" bordered>
          <Table<SchedulerJob>
            rowKey="jobId"
            columns={jobColumns}
            dataSource={jobs}
            loading={loading}
            pagination={false}
            scroll={{ x: 1100 }}
          />
        </ProCard>

        <ProCard title="执行历史" bordered>
          <Table<SchedulerRun>
            rowKey="id"
            columns={runColumns}
            dataSource={runs}
            loading={loading}
            pagination={{ pageSize: 20 }}
            scroll={{ x: 1200 }}
          />
        </ProCard>
      </Space>
    </PageContainer>
  );
}
