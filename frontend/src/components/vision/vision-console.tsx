"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, Button, Card, Descriptions, Image, Space, Table, Tag, Typography, Upload } from "antd";
import type { UploadProps } from "antd";

import {
  fetchVisionRuntime,
  fetchVisionTask,
  fetchVisionTasks,
  fetchVisionWebSocketUrl,
  submitVisionTask,
  VisionApiError,
} from "@/src/lib/api/vision";
import type { VisionRuntimePayload, VisionTask, VisionTaskEventPayload } from "@/src/types/vision";

function statusTag(status: VisionTask["status"]) {
  if (status === "DONE") return <Tag color="success">DONE</Tag>;
  if (status === "FAILED") return <Tag color="error">FAILED</Tag>;
  return <Tag color="processing">PROCESSING</Tag>;
}

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const normalized = hasTimezone ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}

function formatConfidence(value?: number | null) {
  if (value === undefined || value === null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function resolveTaskImageSrc(imageUrl?: string | null) {
  if (!imageUrl) return undefined;
  if (imageUrl.startsWith("http://") || imageUrl.startsWith("https://") || imageUrl.startsWith("data:")) {
    return imageUrl;
  }
  if (imageUrl.startsWith("/files/")) {
    const filePath = imageUrl
      .replace(/^\/files\//, "")
      .split("/")
      .filter(Boolean)
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    return `/api/vision/files/${filePath}`;
  }
  const relativePath = imageUrl
    .replace(/^\/+/, "")
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  if (!relativePath) return undefined;
  return `/api/vision/files/${relativePath}`;
}

export function VisionConsole() {
  const [runtime, setRuntime] = useState<VisionRuntimePayload | null>(null);
  const [tasks, setTasks] = useState<VisionTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedImageKeys, setFailedImageKeys] = useState<Set<string>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);

  const getImageKey = useCallback((task: VisionTask) => `${task.taskId}:${task.imageUrl || ""}`, []);

  const upsertTask = useCallback((incoming: VisionTask) => {
    setTasks((prev) => {
      const next = [incoming, ...prev.filter((item) => item.taskId !== incoming.taskId)];
      next.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      return next.slice(0, 20);
    });
  }, []);

  const refreshTasks = useCallback(async () => {
    const payload = await fetchVisionTasks(20);
    setTasks(payload.items);
  }, []);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    try {
      const [runtimePayload, tasksPayload] = await Promise.all([
        fetchVisionRuntime(),
        fetchVisionTasks(20),
      ]);
      setRuntime(runtimePayload);
      setTasks(tasksPayload.items);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "病害识别模块加载失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    let disposed = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (disposed) {
        return;
      }
      clearReconnectTimer();
      const attempt = reconnectAttemptRef.current + 1;
      reconnectAttemptRef.current = attempt;
      const delay = Math.min(10_000, 1_000 * 2 ** Math.min(attempt, 4));
      reconnectTimerRef.current = window.setTimeout(() => {
        void connectWebSocket();
      }, delay);
    };

    const handleMessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as VisionTaskEventPayload;
        if (payload.runtime) {
          setRuntime(payload.runtime);
        }
        if (payload.task) {
          upsertTask(payload.task);
        }
      } catch {
        // Ignore malformed events so websocket stream can continue.
      }
    };

    const connectWebSocket = async () => {
      try {
        const wsUrl = await fetchVisionWebSocketUrl();
        if (disposed) {
          return;
        }
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          reconnectAttemptRef.current = 0;
          setError(null);
        };
        socket.onmessage = handleMessage;
        socket.onerror = () => {
          socket.close();
        };
        socket.onclose = () => {
          if (wsRef.current === socket) {
            wsRef.current = null;
          }
          scheduleReconnect();
        };
      } catch (wsError) {
        if (!disposed) {
          setError(wsError instanceof Error ? wsError.message : "实时推送连接失败。");
          scheduleReconnect();
        }
      }
    };

    void connectWebSocket();

    return () => {
      disposed = true;
      clearReconnectTimer();
      const socket = wsRef.current;
      wsRef.current = null;
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [upsertTask]);

  const uploadProps: UploadProps = {
    accept: "image/*",
    multiple: false,
    showUploadList: false,
    customRequest: async (options) => {
      const file = options.file;
      if (!(file instanceof File)) {
        options.onError?.(new Error("仅支持图片文件上传。"));
        return;
      }

      setUploading(true);
      try {
        const created = await submitVisionTask(file);
        setTasks((prev) => [created, ...prev.filter((item) => item.taskId !== created.taskId)].slice(0, 20));
        setError(null);
        options.onSuccess?.(created, new XMLHttpRequest());
      } catch (submitError) {
        const message = submitError instanceof Error ? submitError.message : "提交识别任务失败。";
        setError(message);
        options.onError?.(new Error(message));
      } finally {
        setUploading(false);
      }
    },
  };

  const columns = [
    {
      title: "任务ID",
      dataIndex: "taskId",
      key: "taskId",
      width: 230,
      render: (value: string) => <Typography.Text code>{value.slice(0, 8)}...</Typography.Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 130,
      render: (value: VisionTask["status"]) => statusTag(value),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 100,
    },
    {
      title: "病害类型",
      dataIndex: "diseaseType",
      key: "diseaseType",
      width: 180,
      render: (value: string | null | undefined) => value || "--",
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 140,
      render: (value: number | null | undefined) => formatConfidence(value),
    },
    {
      title: "引擎/设备",
      key: "runtime",
      width: 180,
      render: (_: unknown, task: VisionTask) => `${task.engine || "--"} / ${task.device || "--"}`,
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      key: "createdAt",
      width: 190,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: "完成时间",
      dataIndex: "processedAt",
      key: "processedAt",
      width: 190,
      render: (value: string | null | undefined) => formatDateTime(value),
    },
  ];

  const firstTask = tasks[0];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {error ? (
        <Alert
          type="warning"
          showIcon
          message="病害识别提示"
          description={error}
          action={
            <Button size="small" onClick={() => void loadInitial()}>
              重试
            </Button>
          }
        />
      ) : null}

      <Card
        title="病害识别任务提交"
        extra={
          <Space>
            <Button loading={loading} onClick={() => void loadInitial()}>
              刷新
            </Button>
            <Button loading={uploading} type="primary" onClick={() => void refreshTasks()}>
              仅刷新任务
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Upload.Dragger {...uploadProps} disabled={uploading}>
            <Typography.Title level={5} style={{ margin: 0 }}>
              点击或拖拽图片到此处上传
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              上传后接口会立即返回受理状态，后台异步识别并自动刷新任务结果。
            </Typography.Paragraph>
          </Upload.Dragger>

          <Descriptions
            title="运行时状态"
            size="small"
            bordered
            column={4}
            items={[
              { key: "mode", label: "模式", children: runtime?.mode || "--" },
              { key: "engine", label: "引擎", children: runtime?.engine || "--" },
              { key: "device", label: "设备", children: runtime?.activeDevice || "--" },
              { key: "storage", label: "存储", children: runtime?.storageBackend || "--" },
              { key: "queue", label: "队列", children: runtime?.queueKey || "--" },
              { key: "depth", label: "队列深度", children: runtime?.queueDepth ?? "--" },
              { key: "maxUpload", label: "上传上限", children: runtime ? `${runtime.maxUploadMb} MB` : "--" },
              { key: "fallback", label: "是否回退", children: runtime?.fallbackOccurred ? "是" : "否" },
            ]}
          />
        </Space>
      </Card>

      <Card title="识别任务列表" loading={loading}>
        <Table<VisionTask>
          rowKey="taskId"
          dataSource={tasks}
          columns={columns}
          pagination={false}
          scroll={{ x: 1300 }}
          expandable={{
            expandedRowRender: (task) => (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {task.imageUrl ? (
                  (() => {
                    const imageSrc = resolveTaskImageSrc(task.imageUrl);
                    const imageKey = getImageKey(task);
                    const shouldShowImage = Boolean(imageSrc) && !failedImageKeys.has(imageKey);

                    if (!shouldShowImage) {
                      return (
                        <div
                          style={{
                            width: 220,
                            height: 132,
                            border: "1px dashed #d9d9d9",
                            borderRadius: 8,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#8c8c8c",
                            background: "#fafafa",
                          }}
                        >
                          图片不可用
                        </div>
                      );
                    }

                    return (
                      <Image
                        src={imageSrc}
                        alt={task.taskId}
                        width={220}
                        onError={() => {
                          setFailedImageKeys((prev) => {
                            if (prev.has(imageKey)) return prev;
                            const next = new Set(prev);
                            next.add(imageKey);
                            return next;
                          });
                        }}
                      />
                    );
                  })()
                ) : null}
                {task.error ? <Alert type="error" showIcon message={task.error} /> : null}
                <Typography.Text>
                  检测框数量：{task.detections.length}，最近更新时间：{formatDateTime(task.updatedAt)}
                </Typography.Text>
                <Button
                  size="small"
                  onClick={async () => {
                    try {
                      const latest = await fetchVisionTask(task.taskId);
                      setTasks((prev) => prev.map((item) => (item.taskId === latest.taskId ? latest : item)));
                      setError(null);
                    } catch (taskError) {
                      if (taskError instanceof VisionApiError) {
                        setError(taskError.message);
                        return;
                      }
                      setError(taskError instanceof Error ? taskError.message : "刷新任务详情失败。");
                    }
                  }}
                >
                  刷新此任务
                </Button>
              </Space>
            ),
          }}
        />
      </Card>

      {firstTask ? (
        <Card title="最近任务摘要">
          <Descriptions
            column={3}
            bordered
            size="small"
            items={[
              { key: "taskId", label: "任务ID", children: firstTask.taskId },
              { key: "status", label: "状态", children: statusTag(firstTask.status) },
              { key: "source", label: "来源", children: firstTask.source },
              { key: "disease", label: "病害类型", children: firstTask.diseaseType || "--" },
              { key: "confidence", label: "置信度", children: formatConfidence(firstTask.confidence) },
              { key: "queuedAt", label: "入队时间", children: formatDateTime(firstTask.queuedAt) },
            ]}
          />
        </Card>
      ) : null}
    </Space>
  );
}
