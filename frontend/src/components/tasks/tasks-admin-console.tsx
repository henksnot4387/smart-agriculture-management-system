"use client";

import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import { fetchTasks } from "@/src/lib/api/tasks";
import type { TaskItem, TaskSource, TaskStatus } from "@/src/types/task";

type TasksAdminConsoleProps = {
  userRole: string;
};

export function TasksAdminConsole({ userRole }: TasksAdminConsoleProps) {
  const [items, setItems] = useState<TaskItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | undefined>(undefined);
  const [sourceFilter, setSourceFilter] = useState<TaskSource | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await fetchTasks({
        assignedTo: "all",
        status: statusFilter,
        source: sourceFilter,
        limit: 200,
      });
      setItems(payload.items);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "任务中心加载失败。");
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: ColumnsType<TaskItem> = [
    {
      title: "任务标题",
      dataIndex: "title",
      key: "title",
      width: 300,
      render: (_, task) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{task.title}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {task.description || "无描述"}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 130,
      render: (status) => <Tag color="processing">{String(status)}</Tag>,
    },
    {
      title: "优先级",
      dataIndex: "priority",
      key: "priority",
      width: 120,
      render: (priority) => (
        <Tag color={priority === "HIGH" ? "red" : priority === "LOW" ? "default" : "orange"}>{String(priority)}</Tag>
      ),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 120,
    },
    {
      title: "创建者",
      key: "createdByEmail",
      width: 180,
      render: (_, task) => task.createdByEmail || "--",
    },
    {
      title: "执行者",
      key: "assigneeEmail",
      width: 180,
      render: (_, task) => task.assigneeEmail || "--",
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      key: "createdAt",
      width: 180,
      render: (value) => new Date(String(value)).toLocaleString("zh-CN", { hour12: false }),
    },
    {
      title: "更新时间",
      dataIndex: "updatedAt",
      key: "updatedAt",
      width: 180,
      render: (value) => new Date(String(value)).toLocaleString("zh-CN", { hour12: false }),
    },
  ];

  return (
    <PageContainer
      title="任务中心"
      subTitle={`当前角色：${userRole}，用于全量追踪任务状态流转。`}
      extra={[
        <Button key="reload" onClick={() => void load()} loading={loading}>
          刷新
        </Button>,
      ]}
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {error ? <Alert type="error" showIcon message="加载失败" description={error} /> : null}

        <ProCard bordered>
          <Space size={10} wrap style={{ marginBottom: 12 }}>
            <Select<TaskStatus | undefined>
              allowClear
              placeholder="状态过滤"
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
              style={{ width: 180 }}
              options={[
                { label: "PENDING", value: "PENDING" },
                { label: "APPROVED", value: "APPROVED" },
                { label: "IN_PROGRESS", value: "IN_PROGRESS" },
                { label: "COMPLETED", value: "COMPLETED" },
              ]}
            />
            <Select<TaskSource | undefined>
              allowClear
              placeholder="来源过滤"
              value={sourceFilter}
              onChange={(value) => setSourceFilter(value)}
              style={{ width: 180 }}
              options={[
                { label: "AI", value: "AI" },
                { label: "MANUAL", value: "MANUAL" },
                { label: "EXTERNAL", value: "EXTERNAL" },
              ]}
            />
          </Space>
          <Table<TaskItem>
            rowKey="taskId"
            loading={loading}
            dataSource={items}
            columns={columns}
            pagination={{ pageSize: 12, showSizeChanger: false }}
            scroll={{ x: 1400 }}
          />
        </ProCard>
      </Space>
    </PageContainer>
  );
}
