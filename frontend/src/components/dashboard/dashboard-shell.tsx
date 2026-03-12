"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Alert, Col, Descriptions, List, Row, Space, Statistic, Tag, Typography } from "antd";
import { PageContainer, ProCard } from "@ant-design/pro-components";

import { SensorLineChart } from "@/src/components/charts/sensor-line-chart";
import { DashboardEmptyState } from "@/src/components/dashboard/dashboard-empty-state";
import { DashboardErrorBanner } from "@/src/components/dashboard/dashboard-error-banner";
import { DashboardHeader } from "@/src/components/dashboard/dashboard-header";
import { MetricCard } from "@/src/components/dashboard/metric-card";
import { DashboardApiError, fetchDashboardHome, triggerDashboardSync } from "@/src/lib/api/dashboard-home";
import { fetchOpsCatalog, fetchOpsLive } from "@/src/lib/api/ops";
import { getGreenhouseDisplayMeta } from "@/src/config/greenhouse";
import type { DashboardHomePayload, DashboardRange, GreenhouseOverviewItem, MetricKey, MetricSummary } from "@/src/types/sensor";
import type { OpsCatalogPayload, OpsLivePayload, OpsZoneSnapshot } from "@/src/types/ops";

const metricOrder: MetricKey[] = ["temperature", "humidity", "ec", "ph"];
const chartMeta: Record<MetricKey, { title: string; color: string; unit: string }> = {
  temperature: { title: "温度趋势", color: "#ea580c", unit: "°C" },
  humidity: { title: "湿度趋势", color: "#0f766e", unit: "%" },
  ec: { title: "EC 趋势", color: "#65a30d", unit: "mS/cm" },
  ph: { title: "pH 趋势", color: "#0369a1", unit: "pH" },
};
const pollingIntervalMs = 30_000;
const staleDataThresholdMs = 10 * 60 * 1000;
const minSyncRetryGapMs = 3 * 60 * 1000;

function formatOpsMetric(value: number, unit: string, valueType: string) {
  if (valueType === "status") {
    return value >= 0.5 ? "开启/激活" : "关闭/未激活";
  }
  if (valueType === "percentage") {
    return `${value.toFixed(1)} %`;
  }
  if (unit === "°C") return `${value.toFixed(1)} °C`;
  if (unit === "%") return `${value.toFixed(1)} %`;
  if (unit === "mS/cm") return `${value.toFixed(2)} mS/cm`;
  if (unit === "pH") return `${value.toFixed(2)} pH`;
  if (unit === "ppm") return `${value.toFixed(0)} ppm`;
  if (unit === "W/m²") return `${value.toFixed(0)} W/m²`;
  if (unit === "m/s") return `${value.toFixed(1)} m/s`;
  if (unit === "°") return `${value.toFixed(0)} °`;
  if (unit === "mm") return `${value.toFixed(2)} mm`;
  if (unit === "count") return `${value.toFixed(0)} 次`;
  if (unit === "raw") return `${value.toFixed(3)}`;
  return `${value.toFixed(3)} ${unit}`;
}

function formatMetricValue(metric: MetricKey, value?: number) {
  if (value === undefined) {
    return "--";
  }

  if (metric === "temperature") {
    return `${value.toFixed(1)} °C`;
  }
  if (metric === "humidity") {
    return `${value.toFixed(1)} %`;
  }
  if (metric === "ec") {
    return `${value.toFixed(2)} mS/cm`;
  }
  return `${value.toFixed(2)} pH`;
}

function DashboardSkeleton() {
  return (
    <Row gutter={[16, 16]}>
      {Array.from({ length: 6 }).map((_, index) => (
        <Col span={24} key={index}>
          <div style={{ height: 180, borderRadius: 20, background: "rgba(255,255,255,0.72)", animation: "pulse 1.8s ease-in-out infinite" }} />
        </Col>
      ))}
    </Row>
  );
}

function GreenhouseStatusCard({ item }: { item: GreenhouseOverviewItem }) {
  const statusColor =
    item.status === "正常" ? "success" : item.status === "部分采集" ? "processing" : "warning";
  const visibleMetrics: MetricKey[] = item.category === "fertigation" ? ["ec", "ph"] : ["temperature", "humidity"];

  return (
    <ProCard bordered>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <Typography.Text type="secondary">{item.group}</Typography.Text>
          <Typography.Title level={4} style={{ marginTop: 4, marginBottom: 0 }}>
            {item.displayName}
          </Typography.Title>
        </div>
        <Tag color={statusColor}>{item.status}</Tag>
      </div>

      <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 16 }}>
        最近采样：{item.latestAtLocal ? new Date(item.latestAtLocal).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }) : "暂无"}
      </Typography.Paragraph>

      <Descriptions column={2} size="small" colon={false}>
        {visibleMetrics.map((metric) => (
          <Descriptions.Item
            key={`${item.zone}-${metric}`}
            label={metric === "temperature" ? "温度" : metric === "humidity" ? "湿度" : metric === "ec" ? "EC" : "pH"}
          >
            {formatMetricValue(metric, item.metrics[metric])}
          </Descriptions.Item>
        ))}
      </Descriptions>
    </ProCard>
  );
}

function OpsZoneTableCard({
  title,
  zones,
  moduleFilter,
}: {
  title: string;
  zones: OpsZoneSnapshot[];
  moduleFilter: (module: string) => boolean;
}) {
  const rows = zones
    .map((zone) => {
      const meta = getGreenhouseDisplayMeta(zone.zone);
      const moduleMetrics = zone.metrics.filter((metric) => moduleFilter(metric.module));
      return {
        zone: zone.zone,
        displayName: meta.displayName,
        order: meta.order,
        latestSampleAtLocal: zone.latestSampleAtLocal,
        metrics: moduleMetrics.slice(0, 8),
      };
    })
    .filter((item) => item.metrics.length > 0)
    .sort((left, right) => left.order - right.order);

  return (
    <ProCard title={title} bordered>
      <List
        dataSource={rows}
        locale={{ emptyText: "暂无可展示数据" }}
        renderItem={(item) => (
          <List.Item>
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              <Space wrap>
                <Typography.Text strong>{item.displayName}</Typography.Text>
                <Typography.Text type="secondary">最新采样：{item.latestSampleAtLocal || "--"}</Typography.Text>
              </Space>
              <Space wrap>
                {item.metrics.map((metric) => (
                  <Tag key={`${item.zone}-${metric.metricKey}`}>
                    {metric.displayName}：{formatOpsMetric(metric.value, metric.unit, metric.valueType)}
                  </Tag>
                ))}
              </Space>
            </Space>
          </List.Item>
        )}
      />
    </ProCard>
  );
}

export function DashboardShell() {
  const [range, setRange] = useState<DashboardRange>("24h");
  const [data, setData] = useState<DashboardHomePayload | null>(null);
  const [opsLive, setOpsLive] = useState<OpsLivePayload | null>(null);
  const [opsCatalog, setOpsCatalog] = useState<OpsCatalogPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const requestIdRef = useRef(0);
  const dataRef = useRef<DashboardHomePayload | null>(null);
  const opsLiveRef = useRef<OpsLivePayload | null>(null);
  const lastSyncAttemptRef = useRef(0);
  const isSyncingRef = useRef(false);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);
  useEffect(() => {
    opsLiveRef.current = opsLive;
  }, [opsLive]);

  const loadDashboard = useCallback(async (nextRange: DashboardRange) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const hasExistingData = Boolean(dataRef.current);

    if (!hasExistingData) {
      setIsInitialLoading(true);
    } else {
      setIsRefreshing(true);
    }

    try {
      let payload: DashboardHomePayload;
      let livePayload: OpsLivePayload | null = null;
      let catalogPayload: OpsCatalogPayload | null = null;
      [payload, livePayload, catalogPayload] = await Promise.all([
        fetchDashboardHome(nextRange),
        fetchOpsLive(24),
        fetchOpsCatalog(24),
      ]);
      const latestUtcCandidates = metricOrder
        .map((metric) => payload.dashboard.summary[metric]?.latestAtUtc)
        .filter((value): value is string => Boolean(value))
        .map((value) => new Date(value).getTime())
        .filter((value) => Number.isFinite(value));
      const latestDataAt = latestUtcCandidates.length > 0 ? Math.max(...latestUtcCandidates) : null;
      const dataIsStale = latestDataAt === null || Date.now() - latestDataAt > staleDataThresholdMs;
      const canRetrySync = Date.now() - lastSyncAttemptRef.current > minSyncRetryGapMs;

      if (dataIsStale && canRetrySync && !isSyncingRef.current) {
        isSyncingRef.current = true;
        lastSyncAttemptRef.current = Date.now();
        try {
          await triggerDashboardSync();
          const [dashboardAfterSync, liveAfterSync, catalogAfterSync] = await Promise.all([
            fetchDashboardHome(nextRange),
            fetchOpsLive(24),
            fetchOpsCatalog(24),
          ]);
          payload = dashboardAfterSync;
          livePayload = liveAfterSync;
          catalogPayload = catalogAfterSync;
        } catch (syncError) {
          if (syncError instanceof DashboardApiError && syncError.status === 401) {
            window.location.href = "/login";
            return;
          }
        } finally {
          isSyncingRef.current = false;
        }
      }

      if (requestId !== requestIdRef.current) {
        return;
      }
      setData(payload);
      setOpsLive(livePayload);
      setOpsCatalog(catalogPayload);
      setError(null);
      setLastUpdated(new Date().toISOString());
    } catch (fetchError) {
      if (requestId !== requestIdRef.current) {
        return;
      }
      if (fetchError instanceof DashboardApiError && fetchError.status === 401) {
        window.location.href = "/login";
        return;
      }
      setError(fetchError instanceof Error ? fetchError.message : "首页数据加载失败。");
    } finally {
      if (requestId === requestIdRef.current) {
        setIsInitialLoading(false);
        setIsRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadDashboard(range);
  }, [loadDashboard, range]);

  useEffect(() => {
    let disposed = false;

    const runPollingCycle = () => {
      if (disposed || document.visibilityState !== "visible") {
        return;
      }
      void loadDashboard(range);
    };

    const intervalId = window.setInterval(runPollingCycle, pollingIntervalMs);
    const handleVisibilityChange = () => {
      if (!disposed && document.visibilityState === "visible") {
        void loadDashboard(range);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      disposed = true;
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [loadDashboard, range]);

  const hasSummary = useMemo(() => metricOrder.some((metric) => Boolean(data?.dashboard.summary?.[metric])), [data]);
  const latestSampleAtLocal = useMemo(() => {
    if (opsLive?.meta?.latestSampleAtLocal) {
      return opsLive.meta.latestSampleAtLocal;
    }
    if (!data) return null;
    const summaryItems = metricOrder
      .map((metric) => data.dashboard.summary?.[metric])
      .filter((item): item is MetricSummary => Boolean(item));
    if (!summaryItems.length) return null;
    const latestItem = summaryItems.reduce((current, candidate) =>
      new Date(candidate.latestAtUtc).getTime() > new Date(current.latestAtUtc).getTime() ? candidate : current,
    );
    return latestItem.latestAtLocal || null;
  }, [data, opsLive]);
  const greenhouseZones = useMemo(
    () => (data?.zones || []).filter((zone) => zone.category === "greenhouse"),
    [data],
  );
  const fertigationZones = useMemo(
    () => (data?.zones || []).filter((zone) => zone.category === "fertigation"),
    [data],
  );
  const opsZones = useMemo(() => opsLive?.zones || [], [opsLive]);

  return (
    <PageContainer header={{ title: false, breadcrumb: {} }}>
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Row gutter={[12, 12]} style={{ alignItems: "stretch" }}>
          <Col xs={24} xl={12} style={{ display: "flex" }}>
            <DashboardHeader
              range={range}
              isRefreshing={isRefreshing}
              lastUpdated={lastUpdated}
              latestSampleAtLocal={latestSampleAtLocal}
              onRefresh={() => void loadDashboard(range)}
              onRangeChange={setRange}
            />
          </Col>
          <Col xs={24} xl={12} style={{ display: "flex" }}>
            {!isInitialLoading && data ? (
              <ProCard title="系统运营态势" bordered style={{ height: "100%", width: "100%" }}>
                <Space direction="vertical" size={14} style={{ width: "100%" }}>
                  <Alert
                    type={
                      opsLive?.meta.freshnessStatus === "STALE"
                        ? "error"
                        : opsLive?.meta.freshnessStatus === "WARNING"
                          ? "warning"
                          : "success"
                    }
                    showIcon
                    message={
                      opsLive?.meta.freshnessStatus === "STALE"
                        ? "数据链路已超时"
                        : opsLive?.meta.freshnessStatus === "WARNING"
                          ? "数据链路需要关注"
                          : "数据链路可用"
                    }
                    description={
                      opsLive?.meta.warningMessage ||
                      `当前范围：${range === "24h" ? "近24小时" : "近7天"}，已接入传感器聚合与分区最新值。`
                    }
                  />
                  <Row gutter={[10, 10]}>
                    <Col span={12}>
                      <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
                        <Statistic title="温室分区" value={data.zones.length} suffix="个" valueStyle={{ fontSize: 24 }} />
                      </div>
                    </Col>
                    <Col span={12}>
                      <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
                        <Statistic
                          title="参数目录覆盖率"
                          value={Math.round((opsCatalog?.coverage?.coverageRate || 0) * 100)}
                          suffix="%"
                          valueStyle={{
                            fontSize: 24,
                            color: opsCatalog?.coverage?.gatePassed ? "#16a34a" : "#d97706",
                          }}
                        />
                      </div>
                    </Col>
                  </Row>
                  <Row gutter={[10, 10]}>
                    <Col span={12}>
                      <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
                        <Statistic title="展示时区" value={data.dashboard.meta.timezone} valueStyle={{ fontSize: 22 }} />
                      </div>
                    </Col>
                    <Col span={12}>
                      <div style={{ padding: "10px 12px", borderRadius: 14, background: "rgba(15, 118, 110, 0.06)" }}>
                        <Statistic title="存储时区" value={data.dashboard.meta.storageTimezone} valueStyle={{ fontSize: 22 }} />
                      </div>
                    </Col>
                  </Row>
                </Space>
              </ProCard>
            ) : (
              <div
                style={{
                  height: "100%",
                  width: "100%",
                  minHeight: 240,
                  borderRadius: 16,
                  background: "rgba(255,255,255,0.72)",
                  animation: "pulse 1.8s ease-in-out infinite",
                }}
              />
            )}
          </Col>
        </Row>

        {error ? <DashboardErrorBanner message={error} /> : null}

        {isInitialLoading && !data ? <DashboardSkeleton /> : null}

        {!isInitialLoading && !hasSummary ? <DashboardEmptyState /> : null}

        {!isInitialLoading && data ? (
          <>
            <Row gutter={[12, 12]}>
              {metricOrder.map((metric) => (
                <Col xs={24} sm={12} xl={6} key={metric}>
                  <MetricCard metric={metric} summary={data.dashboard.summary[metric]} />
                </Col>
              ))}
            </Row>

            <Row gutter={[12, 12]}>
              <Col xs={24}>
                <ProCard title="温室分区态势" >
                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={14}>
                      <ProCard type="inner" title={`温室气候分区（${greenhouseZones.length}）`} bordered>
                        <Row gutter={[12, 12]}>
                          {greenhouseZones.map((zone) => (
                            <Col xs={24} md={12} key={zone.zone}>
                              <GreenhouseStatusCard item={zone} />
                            </Col>
                          ))}
                        </Row>
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={10}>
                      <ProCard type="inner" title={`水肥系统（${fertigationZones.length}）`} bordered>
                        <Row gutter={[12, 12]}>
                          {fertigationZones.map((zone) => (
                            <Col xs={24} key={zone.zone}>
                              <GreenhouseStatusCard item={zone} />
                            </Col>
                          ))}
                        </Row>
                      </ProCard>
                    </Col>
                  </Row>
                </ProCard>
              </Col>
            </Row>

            <Row gutter={[12, 12]}>
              <Col xs={24}>
                <ProCard title="设备与执行器实时状态（真实 partner_api）" bordered>
                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={12}>
                      <OpsZoneTableCard
                        title="温室环境与执行器"
                        zones={opsZones}
                        moduleFilter={(module) =>
                          [
                            "greenhouse_environment",
                            "actuator_vent",
                            "actuator_screen",
                            "actuator_fog",
                            "actuator_fan",
                            "heating",
                          ].includes(module)
                        }
                      />
                    </Col>
                    <Col xs={24} xl={12}>
                      <Space direction="vertical" size={12} style={{ width: "100%" }}>
                        <OpsZoneTableCard
                          title="锅炉与室外气象站"
                          zones={opsZones}
                          moduleFilter={(module) => ["boiler", "outdoor_weather"].includes(module)}
                        />
                        <OpsZoneTableCard
                          title="水肥系统"
                          zones={opsZones}
                          moduleFilter={(module) => module === "fertigation"}
                        />
                      </Space>
                    </Col>
                  </Row>
                </ProCard>
              </Col>
            </Row>

            <Row gutter={[12, 12]}>
              {metricOrder.map((metric) => (
                <Col xs={24} xl={12} key={metric}>
                  <SensorLineChart
                    title={chartMeta[metric].title}
                    metric={metric}
                    series={data.dashboard.series[metric] || []}
                    color={chartMeta[metric].color}
                    unit={chartMeta[metric].unit}
                    range={range}
                  />
                </Col>
              ))}
            </Row>

          </>
        ) : null}
      </Space>
    </PageContainer>
  );
}
