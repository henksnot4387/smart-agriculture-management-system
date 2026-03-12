"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Col, Row, Space, Statistic, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import {
  fetchObservabilityErrors,
  fetchObservabilityOverview,
  fetchObservabilitySlowRequests,
  fetchObservabilityTaskFailures,
  ObservabilityApiError,
} from "@/src/lib/api/observability";
import type {
  ObservabilityErrorEvent,
  ObservabilityOverviewPayload,
  ObservabilityTaskFailureMetric,
} from "@/src/types/observability";

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("zh-CN", { hour12: false });
}

function statusTag(statusCode: number) {
  if (statusCode >= 500) return <Tag color="error">{statusCode}</Tag>;
  if (statusCode >= 400) return <Tag color="warning">{statusCode}</Tag>;
  if (statusCode >= 300) return <Tag color="processing">{statusCode}</Tag>;
  return <Tag color="success">{statusCode}</Tag>;
}

export function ObservabilityConsole() {
  const [overview, setOverview] = useState<ObservabilityOverviewPayload | null>(null);
  const [errors, setErrors] = useState<ObservabilityErrorEvent[]>([]);
  const [slowRequests, setSlowRequests] = useState<ObservabilityErrorEvent[]>([]);
  const [taskFailures, setTaskFailures] = useState<ObservabilityTaskFailureMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewPayload, errorsPayload, slowPayload, taskPayload] = await Promise.all([
        fetchObservabilityOverview(24),
        fetchObservabilityErrors(24, 100),
        fetchObservabilitySlowRequests(24, 100),
        fetchObservabilityTaskFailures(24, 50),
      ]);
      setOverview(overviewPayload);
      setErrors(errorsPayload.items);
      setSlowRequests(slowPayload.items);
      setTaskFailures(taskPayload.items);
      setLastUpdatedAt(new Date().toISOString());
      setError(null);
    } catch (loadError) {
      if (loadError instanceof ObservabilityApiError) {
        setError(loadError.message);
      } else if (loadError instanceof Error) {
        setError(loadError.message);
      } else {
        setError("可观测数据加载失败。");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
    const timer = window.setInterval(() => {
      void loadAll();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [loadAll]);

  const routeColumns = useMemo<ColumnsType<NonNullable<ObservabilityOverviewPayload["topRoutes"]>[number]>>(
    () => [
      {
        title: "接口路由",
        dataIndex: "route",
        key: "route",
        width: 260,
        render: (value: string) => <Typography.Text code>{value || "--"}</Typography.Text>,
      },
      {
        title: "请求数",
        dataIndex: "requestCount",
        key: "requestCount",
        width: 110,
      },
      {
        title: "错误数",
        dataIndex: "errorCount",
        key: "errorCount",
        width: 110,
      },
      {
        title: "慢请求数",
        dataIndex: "slowCount",
        key: "slowCount",
        width: 120,
      },
      {
        title: "平均延迟",
        dataIndex: "avgLatencyMs",
        key: "avgLatencyMs",
        width: 140,
        render: (value: number) => `${value.toFixed(2)} ms`,
      },
      {
        title: "P95",
        dataIndex: "p95LatencyMs",
        key: "p95LatencyMs",
        width: 130,
        render: (value: number) => `${value.toFixed(2)} ms`,
      },
      {
        title: "最大延迟",
        dataIndex: "maxLatencyMs",
        key: "maxLatencyMs",
        width: 140,
        render: (value: number) => `${value.toFixed(2)} ms`,
      },
    ],
    [],
  );

  const errorColumns = useMemo<ColumnsType<ObservabilityErrorEvent>>(
    () => [
      {
        title: "时间",
        dataIndex: "occurredAt",
        key: "occurredAt",
        width: 190,
        render: (value: string) => formatDateTime(value),
      },
      {
        title: "请求ID",
        dataIndex: "requestId",
        key: "requestId",
        width: 180,
        render: (value: string) => <Typography.Text code>{value.slice(0, 12)}...</Typography.Text>,
      },
      {
        title: "路由",
        dataIndex: "route",
        key: "route",
        width: 250,
        render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
      },
      {
        title: "状态码",
        dataIndex: "statusCode",
        key: "statusCode",
        width: 100,
        render: (value: number) => statusTag(value),
      },
      {
        title: "错误码",
        dataIndex: "errorCode",
        key: "errorCode",
        width: 200,
        render: (value: string | null | undefined) =>
          value ? <Tag color="warning">{value}</Tag> : <Typography.Text type="secondary">--</Typography.Text>,
      },
      {
        title: "延迟",
        dataIndex: "durationMs",
        key: "durationMs",
        width: 120,
        render: (value: number) => `${value.toFixed(2)} ms`,
      },
      {
        title: "用户",
        key: "actor",
        width: 180,
        render: (_: unknown, record) => {
          if (!record.userId || !record.userRole) {
            return <Typography.Text type="secondary">匿名</Typography.Text>;
          }
          return (
            <Space direction="vertical" size={0}>
              <Typography.Text>{record.userRole}</Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {record.userId.slice(0, 8)}...
              </Typography.Text>
            </Space>
          );
        },
      },
    ],
    [],
  );

  const taskFailureColumns = useMemo<ColumnsType<ObservabilityTaskFailureMetric>>(
    () => [
      {
        title: "任务ID",
        dataIndex: "jobId",
        key: "jobId",
        width: 220,
        render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
      },
      {
        title: "失败次数(24h)",
        dataIndex: "failedCount",
        key: "failedCount",
        width: 130,
      },
      {
        title: "最近失败时间",
        dataIndex: "lastFailedAt",
        key: "lastFailedAt",
        width: 180,
        render: (value: string | null | undefined) => formatDateTime(value),
      },
      {
        title: "最近错误",
        dataIndex: "lastError",
        key: "lastError",
        ellipsis: true,
        render: (value: string | null | undefined) =>
          value ? <Typography.Text>{value}</Typography.Text> : <Typography.Text type="secondary">--</Typography.Text>,
      },
    ],
    [],
  );

  return (
    <PageContainer
      title="可观测中心"
      subTitle="仅超级管理员可用：统一查看请求日志、慢接口、错误链路与 Celery 任务失败统计。"
      extra={[
        <Button key="refresh" loading={loading} onClick={() => void loadAll()}>
          立即刷新
        </Button>,
      ]}
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {error ? <Alert type="warning" showIcon message="可观测加载失败" description={error} /> : null}

        <ProCard>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Statistic title="24h 总请求数" value={overview?.totalRequests ?? 0} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title="24h 错误请求数" value={overview?.errorRequests ?? 0} valueStyle={{ color: "#cf1322" }} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic
                title={`24h 慢请求数 (>${overview?.slowThresholdMs ?? "--"}ms)`}
                value={overview?.slowRequests ?? 0}
                valueStyle={{ color: "#d46b08" }}
              />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title="24h P95 延迟" value={overview?.p95LatencyMs ?? 0} suffix="ms" precision={2} />
            </Col>
          </Row>
          <Typography.Text type="secondary" style={{ marginTop: 8, display: "block" }}>
            最近刷新时间：{formatDateTime(lastUpdatedAt)}
          </Typography.Text>
        </ProCard>

        <ProCard title="慢接口/错误接口排行">
          <Table
            rowKey="route"
            columns={routeColumns}
            dataSource={overview?.topRoutes ?? []}
            loading={loading}
            pagination={false}
            scroll={{ x: 1100 }}
          />
        </ProCard>

        <ProCard title="最近错误请求（24h）">
          <Table
            rowKey={(record) => `${record.requestId}-${record.occurredAt}`}
            columns={errorColumns}
            dataSource={errors}
            loading={loading}
            pagination={{ pageSize: 10 }}
            scroll={{ x: 1400 }}
          />
        </ProCard>

        <ProCard title={`最近慢请求（24h，>${overview?.slowThresholdMs ?? "--"}ms）`}>
          <Table
            rowKey={(record) => `${record.requestId}-${record.occurredAt}`}
            columns={errorColumns}
            dataSource={slowRequests}
            loading={loading}
            pagination={{ pageSize: 10 }}
            scroll={{ x: 1400 }}
          />
        </ProCard>

        <ProCard title="Celery 任务失败排行（24h）">
          <Table
            rowKey="jobId"
            columns={taskFailureColumns}
            dataSource={taskFailures}
            loading={loading}
            pagination={false}
            scroll={{ x: 900 }}
          />
        </ProCard>
      </Space>
    </PageContainer>
  );
}
