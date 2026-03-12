"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import { claimTask, completeTask, fetchTasks, startTask } from "@/src/lib/api/tasks";
import type { CompleteTaskRequest, ExecutionMaterial, OperationType, TaskItem } from "@/src/types/task";

const operationOptions: { label: string; value: OperationType }[] = [
  { label: "灌溉调整", value: "IRRIGATION" },
  { label: "水肥执行", value: "FERTIGATION" },
  { label: "植保处置", value: "PLANT_PROTECTION" },
  { label: "气候调整", value: "CLIMATE_ADJUSTMENT" },
  { label: "巡检复核", value: "INSPECTION" },
  { label: "其他操作", value: "OTHER" },
];

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

type WorkerConsoleProps = {
  userEmail: string;
};

type TaskBuckets = {
  available: TaskItem[];
  readyToStart: TaskItem[];
  inProgress: TaskItem[];
  completed: TaskItem[];
};

const initialBuckets: TaskBuckets = {
  available: [],
  readyToStart: [],
  inProgress: [],
  completed: [],
};

export function WorkerConsole({ userEmail }: WorkerConsoleProps) {
  const [buckets, setBuckets] = useState<TaskBuckets>(initialBuckets);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completingTask, setCompletingTask] = useState<TaskItem | null>(null);
  const [form] = Form.useForm();
  const [submittingComplete, setSubmittingComplete] = useState(false);
  const [api, contextHolder] = message.useMessage();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [approvedUnassigned, approvedMine, inProgressMine, completedMine] = await Promise.all([
        fetchTasks({ status: "APPROVED", assignedTo: "unassigned", limit: 100 }),
        fetchTasks({ status: "APPROVED", assignedTo: "me", limit: 100 }),
        fetchTasks({ status: "IN_PROGRESS", assignedTo: "me", limit: 100 }),
        fetchTasks({ status: "COMPLETED", assignedTo: "me", limit: 100 }),
      ]);

      const mergedAvailable = [...approvedMine.items];
      for (const item of approvedUnassigned.items) {
        if (!mergedAvailable.find((current) => current.taskId === item.taskId)) {
          mergedAvailable.push(item);
        }
      }

      setBuckets({
        available: mergedAvailable,
        readyToStart: approvedMine.items,
        inProgress: inProgressMine.items,
        completed: completedMine.items,
      });
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "工人任务加载失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const baseColumns: ColumnsType<TaskItem> = [
    {
      title: "任务",
      dataIndex: "title",
      key: "title",
      width: 280,
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
      title: "优先级",
      dataIndex: "priority",
      key: "priority",
      width: 120,
      render: (priority) => (
        <Tag color={priority === "HIGH" ? "red" : priority === "LOW" ? "default" : "orange"}>{String(priority)}</Tag>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 140,
      render: (value) => <Tag color="processing">{String(value)}</Tag>,
    },
    {
      title: "指派",
      key: "assignee",
      width: 200,
      render: (_, task) => (
        <Typography.Text type="secondary">{task.assigneeEmail || "未指派（可接单）"}</Typography.Text>
      ),
    },
    {
      title: "更新时间",
      dataIndex: "updatedAt",
      key: "updatedAt",
      width: 180,
      render: (value) => new Date(String(value)).toLocaleString("zh-CN", { hour12: false }),
    },
  ];

  const availableColumns: ColumnsType<TaskItem> = [
    ...baseColumns,
    {
      title: "操作",
      key: "actions",
      width: 160,
      fixed: "right",
      render: (_, task) =>
        task.assigneeId ? (
          <Button
            type="primary"
            size="small"
            onClick={async () => {
              try {
                await startTask(task.taskId);
                api.success("任务已开始执行。");
                await load();
              } catch (actionError) {
                api.error(actionError instanceof Error ? actionError.message : "开始执行失败。");
              }
            }}
          >
            开始执行
          </Button>
        ) : (
          <Button
            size="small"
            onClick={async () => {
              try {
                await claimTask(task.taskId);
                api.success("接单成功。");
                await load();
              } catch (actionError) {
                api.error(actionError instanceof Error ? actionError.message : "接单失败。");
              }
            }}
          >
            接单
          </Button>
        ),
    },
  ];

  const inProgressColumns: ColumnsType<TaskItem> = [
    ...baseColumns,
    {
      title: "操作",
      key: "actions",
      width: 180,
      fixed: "right",
      render: (_, task) => (
        <Button
          type="primary"
          size="small"
          onClick={() => {
            setCompletingTask(task);
            form.resetFields();
            form.setFieldsValue({
              operationType: "INSPECTION",
            });
          }}
        >
          填写完工回填
        </Button>
      ),
    },
  ];

  const completeSubmit = useCallback(async () => {
    if (!completingTask) return;
    const values = await form.validateFields();

    const materials: ExecutionMaterial[] = ((values.materials || []) as ExecutionMaterial[])
      .filter((item) => item && item.name && item.unit && item.amount !== undefined)
      .map((item) => ({
        name: String(item.name).trim(),
        unit: String(item.unit).trim(),
        amount: Number(item.amount),
      }));

    const payload: CompleteTaskRequest = {
      operationType: values.operationType as OperationType,
      executedActions: parseLines(String(values.executedActions || "")),
      readingsBefore: {
        temperature: values.beforeTemperature ?? null,
        humidity: values.beforeHumidity ?? null,
        ec: values.beforeEc ?? null,
        ph: values.beforePh ?? null,
      },
      readingsAfter: {
        temperature: values.afterTemperature ?? null,
        humidity: values.afterHumidity ?? null,
        ec: values.afterEc ?? null,
        ph: values.afterPh ?? null,
      },
      materials,
      anomalies: parseLines(String(values.anomalies || "")),
      resultSummary: String(values.resultSummary || ""),
      attachments: parseLines(String(values.attachments || "")),
    };

    setSubmittingComplete(true);
    try {
      await completeTask(completingTask.taskId, payload);
      api.success("完工提交成功，任务已变更为 COMPLETED。");
      setCompletingTask(null);
      form.resetFields();
      await load();
    } catch (submitError) {
      api.error(submitError instanceof Error ? submitError.message : "完工提交失败。");
    } finally {
      setSubmittingComplete(false);
    }
  }, [api, completingTask, form, load]);

  return (
    <PageContainer
      title="工人执行"
      subTitle={`当前账号：${userEmail}。按“接单 -> 开始执行 -> 完工回填”完成闭环。`}
      extra={[
        <Button key="refresh" onClick={() => void load()} loading={loading}>
          刷新
        </Button>,
      ]}
    >
      {contextHolder}
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {error ? <Alert type="error" showIcon message="加载失败" description={error} /> : null}

        <ProCard title={`可接单/待开始（${buckets.available.length}）`} bordered>
          <Table<TaskItem>
            rowKey="taskId"
            loading={loading}
            dataSource={buckets.available}
            columns={availableColumns}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1250 }}
          />
        </ProCard>

        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <ProCard title={`执行中（${buckets.inProgress.length}）`} bordered>
              <Table<TaskItem>
                rowKey="taskId"
                loading={loading}
                dataSource={buckets.inProgress}
                columns={inProgressColumns}
                pagination={{ pageSize: 5, showSizeChanger: false }}
                scroll={{ x: 1100 }}
              />
            </ProCard>
          </Col>
          <Col xs={24} lg={12}>
            <ProCard title={`已完成（${buckets.completed.length}）`} bordered>
              <Table<TaskItem>
                rowKey="taskId"
                loading={loading}
                dataSource={buckets.completed}
                columns={baseColumns}
                pagination={{ pageSize: 5, showSizeChanger: false }}
                scroll={{ x: 950 }}
              />
            </ProCard>
          </Col>
        </Row>
      </Space>

      <Modal
        open={Boolean(completingTask)}
        title="结构化完工回填"
        width={900}
        onCancel={() => {
          setCompletingTask(null);
          form.resetFields();
        }}
        onOk={() => void completeSubmit()}
        confirmLoading={submittingComplete}
        okText="提交完工"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Row gutter={[10, 10]}>
            <Col span={12}>
              <Form.Item name="operationType" label="操作类型" rules={[{ required: true, message: "请选择操作类型" }]}>
                <Select options={operationOptions} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="resultSummary"
                label="结果总结"
                rules={[{ required: true, min: 8, message: "结果总结至少 8 个字" }]}
              >
                <Input placeholder="例如：完成阀组调整后 EC 回落并稳定，病害风险下降。" />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item
                name="executedActions"
                label="执行动作（每行一条）"
                rules={[{ required: true, message: "请至少填写一条执行动作" }]}
              >
                <Input.TextArea rows={3} placeholder={"例如：\n调整 2 号区灌溉阀门\n执行叶面喷施"} />
              </Form.Item>
            </Col>

            <Col span={12}>
              <Typography.Text strong>执行前读数</Typography.Text>
              <Row gutter={[8, 8]}>
                <Col span={12}>
                  <Form.Item name="beforeTemperature" label="温度(°C)">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="beforeHumidity" label="湿度(%)">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="beforeEc" label="EC(mS/cm)">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="beforePh" label="pH">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
            </Col>

            <Col span={12}>
              <Typography.Text strong>执行后读数</Typography.Text>
              <Row gutter={[8, 8]}>
                <Col span={12}>
                  <Form.Item name="afterTemperature" label="温度(°C)">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="afterHumidity" label="湿度(%)">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="afterEc" label="EC(mS/cm)">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="afterPh" label="pH">
                    <InputNumber style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
              </Row>
            </Col>

            <Col span={24}>
              <Form.List name="materials">
                {(fields, { add, remove }) => (
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    <Space>
                      <Typography.Text strong>使用物料（可选）</Typography.Text>
                      <Button onClick={() => add()} size="small">
                        新增物料
                      </Button>
                    </Space>
                    {fields.map((field) => (
                      <Row gutter={[8, 8]} key={field.key}>
                        <Col span={9}>
                          <Form.Item name={[field.name, "name"]} rules={[{ required: true, message: "请输入物料名" }]}>
                            <Input placeholder="物料名称" />
                          </Form.Item>
                        </Col>
                        <Col span={7}>
                          <Form.Item name={[field.name, "amount"]} rules={[{ required: true, message: "请输入数量" }]}>
                            <InputNumber style={{ width: "100%" }} placeholder="数量" />
                          </Form.Item>
                        </Col>
                        <Col span={6}>
                          <Form.Item name={[field.name, "unit"]} rules={[{ required: true, message: "单位" }]}>
                            <Input placeholder="单位" />
                          </Form.Item>
                        </Col>
                        <Col span={2}>
                          <Button danger onClick={() => remove(field.name)}>
                            删
                          </Button>
                        </Col>
                      </Row>
                    ))}
                  </Space>
                )}
              </Form.List>
            </Col>

            <Col span={12}>
              <Form.Item name="anomalies" label="异常记录（每行一条，可选）">
                <Input.TextArea rows={3} placeholder={"例如：\n3号北区喷头短时堵塞"} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="attachments" label="附件URL（每行一条，可选）">
                <Input.TextArea rows={3} placeholder={"例如：\nhttps://example.com/file1.jpg"} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </PageContainer>
  );
}
