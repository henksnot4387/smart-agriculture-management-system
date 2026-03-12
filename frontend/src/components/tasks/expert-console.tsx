"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Modal, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import { approveTask, fetchTaskAssignees, fetchTasks } from "@/src/lib/api/tasks";
import type { TaskAssigneeOption, TaskItem } from "@/src/types/task";

type ExpertConsoleProps = {
  userRole: string;
};

function getCopilotProvider(task: TaskItem): string {
  const metadata = task.metadata || {};
  const copilot = (metadata.copilot || metadata.aiInsights || {}) as Record<string, unknown>;
  const llm = (copilot.llm || {}) as Record<string, unknown>;
  const provider = String(llm.provider || "fallback").toUpperCase();
  return provider;
}

function getCopilotReason(task: TaskItem): string {
  const metadata = task.metadata || {};
  const copilot = (metadata.copilot || metadata.aiInsights || {}) as Record<string, unknown>;
  return String(copilot.reason || "无");
}

export function ExpertConsole({ userRole }: ExpertConsoleProps) {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [assignees, setAssignees] = useState<TaskAssigneeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approvingTask, setApprovingTask] = useState<TaskItem | null>(null);
  const [selectedAssigneeId, setSelectedAssigneeId] = useState<string | undefined>(undefined);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [api, contextHolder] = message.useMessage();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pendingPayload, assigneePayload] = await Promise.all([
        fetchTasks({ status: "PENDING", assignedTo: "all", limit: 100 }),
        fetchTaskAssignees(),
      ]);
      setTasks(pendingPayload.items);
      setAssignees(assigneePayload.items);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "待审任务加载失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const assigneeOptions = useMemo(
    () =>
      assignees.map((item) => ({
        label: item.name ? `${item.name} (${item.email})` : item.email,
        value: item.id,
      })),
    [assignees],
  );

  const columns: ColumnsType<TaskItem> = [
    {
      title: "任务标题",
      dataIndex: "title",
      key: "title",
      width: 260,
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
      title: "来源",
      key: "source",
      width: 160,
      render: (_, task) => (
        <Space direction="vertical" size={2}>
          <Tag color={task.source === "AI" ? "processing" : "default"}>{task.source}</Tag>
          <Tag color={getCopilotProvider(task) === "DEEPSEEK" ? "success" : "warning"}>{getCopilotProvider(task)}</Tag>
        </Space>
      ),
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
      title: "建议原因",
      key: "reason",
      render: (_, task) => (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {getCopilotReason(task)}
        </Typography.Text>
      ),
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      key: "createdAt",
      width: 180,
      render: (value) => (
        <Typography.Text type="secondary">
          {new Date(String(value)).toLocaleString("zh-CN", { hour12: false })}
        </Typography.Text>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 160,
      fixed: "right",
      render: (_, task) => (
        <Button
          type="primary"
          size="small"
          onClick={() => {
            setApprovingTask(task);
            setSelectedAssigneeId(task.assigneeId || undefined);
          }}
        >
          审批通过
        </Button>
      ),
    },
  ];

  const submitApprove = useCallback(async () => {
    if (!approvingTask) return;
    setSubmitLoading(true);
    try {
      await approveTask(approvingTask.taskId, { assigneeId: selectedAssigneeId || null });
      api.success("审批成功，任务已进入 APPROVED。");
      setApprovingTask(null);
      setSelectedAssigneeId(undefined);
      await load();
    } catch (submitError) {
      api.error(submitError instanceof Error ? submitError.message : "审批失败。");
    } finally {
      setSubmitLoading(false);
    }
  }, [api, approvingTask, load, selectedAssigneeId]);

  return (
    <PageContainer
      title="专家审批"
      subTitle={`当前角色：${userRole}，集中处理 AI 建议和待审批任务。`}
      extra={[
        <Button key="refresh" onClick={() => void load()} loading={loading}>
          刷新
        </Button>,
      ]}
    >
      {contextHolder}
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {error ? <Alert type="error" showIcon message="加载失败" description={error} /> : null}
        <ProCard title={`待审批任务（${tasks.length}）`} bordered>
          <Table<TaskItem>
            rowKey="taskId"
            loading={loading}
            dataSource={tasks}
            columns={columns}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            scroll={{ x: 1200 }}
          />
        </ProCard>
      </Space>

      <Modal
        open={Boolean(approvingTask)}
        title="审批并可选指派工人"
        onCancel={() => {
          setApprovingTask(null);
          setSelectedAssigneeId(undefined);
        }}
        onOk={() => void submitApprove()}
        okText="确认审批"
        cancelText="取消"
        confirmLoading={submitLoading}
      >
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <Typography.Text strong>{approvingTask?.title}</Typography.Text>
          <Typography.Text type="secondary">{approvingTask?.description || "无描述"}</Typography.Text>
          <Typography.Text>可选指派工人（不选则保持未指派，工人可在 /worker 接单）：</Typography.Text>
          <Select
            allowClear
            placeholder="请选择工人（可留空）"
            options={assigneeOptions}
            value={selectedAssigneeId}
            onChange={(value) => setSelectedAssigneeId(value)}
            style={{ width: "100%" }}
          />
        </Space>
      </Modal>
    </PageContainer>
  );
}
