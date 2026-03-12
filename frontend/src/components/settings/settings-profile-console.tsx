"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Button, Form, Input, InputNumber, Select, Space, Switch, Typography, message } from "antd";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import { fetchSettingsProfile, triggerSettingsProfile, updateSettingsProfile } from "@/src/lib/api/settings";
import type { SettingsProfileConfig, SettingsProfileKey } from "@/src/types/settings";

const operationTypeOptions = [
  "IRRIGATION",
  "FERTIGATION",
  "PLANT_PROTECTION",
  "CLIMATE_ADJUSTMENT",
  "INSPECTION",
  "OTHER",
].map((value) => ({ label: value, value }));

const profileNameMap: Record<SettingsProfileKey, string> = {
  horticulture: "园艺设置",
  plant_protection: "植保设置",
  climate: "环控设置",
  fertigation: "水肥设置",
};

type SettingsProfileConsoleProps = {
  profile: SettingsProfileKey;
};

export function SettingsProfileConsole({ profile }: SettingsProfileConsoleProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [lastTriggeredAt, setLastTriggeredAt] = useState<string | null>(null);
  const [lastTaskId, setLastTaskId] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [api, contextHolder] = message.useMessage();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await fetchSettingsProfile(profile);
      setEnabled(payload.item.enabled);
      setLastTriggeredAt(payload.item.lastTriggeredAt || null);
      setLastTaskId(payload.item.lastTaskId || null);
      form.setFieldsValue({
        autoCreateEnabled: payload.item.config.autoCreateEnabled,
        cadenceHours: payload.item.config.cadenceHours,
        title: payload.item.config.taskTemplate.title,
        description: payload.item.config.taskTemplate.description,
        priority: payload.item.config.taskTemplate.priority,
        operationType: payload.item.config.taskTemplate.operationType,
        rulesJson: JSON.stringify(payload.item.config.rules || [], null, 2),
      });
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "加载设置失败。");
    } finally {
      setLoading(false);
    }
  }, [form, profile]);

  useEffect(() => {
    void load();
  }, [load]);

  const title = useMemo(() => profileNameMap[profile], [profile]);

  const handleSave = useCallback(async () => {
    const values = await form.validateFields();
    let rules = [] as Array<Record<string, unknown>>;
    try {
      rules = JSON.parse(values.rulesJson || "[]");
      if (!Array.isArray(rules)) {
        throw new Error("rules 必须是数组。");
      }
    } catch (parseError) {
      api.error(parseError instanceof Error ? parseError.message : "规则 JSON 格式错误。");
      return;
    }
    const config: SettingsProfileConfig = {
      autoCreateEnabled: Boolean(values.autoCreateEnabled),
      cadenceHours: Number(values.cadenceHours),
      taskTemplate: {
        title: String(values.title || "").trim(),
        description: String(values.description || "").trim(),
        priority: values.priority,
        operationType: values.operationType,
      },
      rules,
    };

    setSaving(true);
    try {
      const updated = await updateSettingsProfile(profile, { enabled, config });
      setLastTriggeredAt(updated.item.lastTriggeredAt || null);
      setLastTaskId(updated.item.lastTaskId || null);
      api.success("设置保存成功。");
    } catch (saveError) {
      api.error(saveError instanceof Error ? saveError.message : "设置保存失败。");
    } finally {
      setSaving(false);
    }
  }, [api, enabled, form, profile]);

  const handleTrigger = useCallback(async () => {
    setTriggering(true);
    try {
      const result = await triggerSettingsProfile(profile);
      if (result.triggered) {
        api.success(`触发成功，任务ID：${result.taskId}`);
      } else {
        api.warning(result.message);
      }
      await load();
    } catch (triggerError) {
      api.error(triggerError instanceof Error ? triggerError.message : "触发失败。");
    } finally {
      setTriggering(false);
    }
  }, [api, load, profile]);

  return (
    <PageContainer title={title} subTitle="配置自动任务触发策略与任务模板。">
      {contextHolder}
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {error ? <Alert type="error" showIcon message="加载失败" description={error} /> : null}
        <ProCard
          bordered
          loading={loading}
          extra={
            <Space>
              <Button onClick={() => void load()} loading={loading}>
                刷新
              </Button>
              <Button onClick={() => void handleTrigger()} loading={triggering}>
                立即触发任务
              </Button>
              <Button type="primary" onClick={() => void handleSave()} loading={saving}>
                保存配置
              </Button>
            </Space>
          }
        >
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Space>
              <Typography.Text>启用配置：</Typography.Text>
              <Switch checked={enabled} onChange={setEnabled} />
            </Space>
            <Typography.Text type="secondary">
              最近触发时间：{lastTriggeredAt ? new Date(lastTriggeredAt).toLocaleString("zh-CN", { hour12: false }) : "--"}
              {"  "}
              最近任务ID：{lastTaskId || "--"}
            </Typography.Text>

            <Form form={form} layout="vertical">
              <Form.Item name="autoCreateEnabled" label="开启自动创建任务" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item name="cadenceHours" label="触发周期（小时）" rules={[{ required: true, message: "请输入触发周期" }]}>
                <InputNumber min={1} max={168} style={{ width: 220 }} />
              </Form.Item>
              <Form.Item name="title" label="任务标题" rules={[{ required: true, message: "请输入任务标题" }]}>
                <Input maxLength={120} />
              </Form.Item>
              <Form.Item name="description" label="任务描述" rules={[{ required: true, message: "请输入任务描述" }]}>
                <Input.TextArea rows={3} maxLength={600} />
              </Form.Item>
              <Form.Item name="priority" label="任务优先级" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: "LOW", value: "LOW" },
                    { label: "MEDIUM", value: "MEDIUM" },
                    { label: "HIGH", value: "HIGH" },
                  ]}
                  style={{ width: 220 }}
                />
              </Form.Item>
              <Form.Item name="operationType" label="操作类型" rules={[{ required: true }]}>
                <Select options={operationTypeOptions} style={{ width: 280 }} />
              </Form.Item>
              <Form.Item name="rulesJson" label="规则配置（JSON数组）">
                <Input.TextArea rows={8} />
              </Form.Item>
            </Form>
          </Space>
        </ProCard>
      </Space>
    </PageContainer>
  );
}
