import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

import { getGreenhouseDisplayMeta } from "@/src/config/greenhouse";
import { getBackendInternalBaseUrl } from "@/src/lib/server/backend-url";
import type { DashboardRange, MetricKey } from "@/src/types/sensor";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const metricKeys: MetricKey[] = ["temperature", "humidity", "ec", "ph"];
const RAW_LIMIT = 20_000; // backend /api/sensor/raw upper bound

function getApiBaseUrl() {
  return getBackendInternalBaseUrl("greenhouse proxy");
}

function getBackendRequestHeaders() {
  const headers: HeadersInit = {
    Accept: "application/json",
  };
  const apiToken = process.env.BACKEND_API_TOKEN;
  if (apiToken) {
    headers["X-API-Token"] = apiToken;
  }
  return headers;
}

function getWindowStart(range: DashboardRange) {
  const end = new Date();
  const start = new Date(end);
  if (range === "7d") {
    start.setDate(end.getDate() - 7);
  } else {
    start.setHours(end.getHours() - 24);
  }

  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}

type RawSample = {
  recordedAtUtc: string;
  recordedAtLocal: string;
  zone: string;
  metric: MetricKey;
  value: number;
};

type ZoneAggregate = {
  zone: string;
  displayName: string;
  group: string;
  area: string;
  category: "greenhouse" | "fertigation";
  latestAtLocal: string | null;
  metrics: Partial<Record<MetricKey, number>>;
  status: "正常" | "部分采集" | "数据缺失";
};

function resolveZoneCategory(displayName: string, area: string): "greenhouse" | "fertigation" {
  if (area === "水肥系统") {
    return "fertigation";
  }
  if (displayName.includes("施肥机") || displayName.includes("水肥")) {
    return "fertigation";
  }
  return "greenhouse";
}

export async function GET(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const range = (request.nextUrl.searchParams.get("range") || "24h") as DashboardRange;
  const { start, end } = getWindowStart(range);

  const params = new URLSearchParams({
    start,
    end,
    metrics: metricKeys.join(","),
    limit: String(RAW_LIMIT),
  });

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/sensor/raw?${params.toString()}`, {
      method: "GET",
      cache: "no-store",
      headers: getBackendRequestHeaders(),
    });

    if (!response.ok) {
      const detail = await response.text();
      return NextResponse.json({ detail: detail || "Failed to load greenhouse overview." }, { status: response.status });
    }

    const payload = (await response.json()) as { items: RawSample[] };
    const latestByZoneMetric = new Map<string, { meta: ReturnType<typeof getGreenhouseDisplayMeta>; samples: Map<MetricKey, RawSample> }>();

    for (const item of payload.items || []) {
      const displayMeta = getGreenhouseDisplayMeta(item.zone);
      const aggregateKey = displayMeta.displayName;
      const aggregate = latestByZoneMetric.get(aggregateKey) ?? {
        meta: displayMeta,
        samples: new Map<MetricKey, RawSample>(),
      };
      const current = aggregate.samples.get(item.metric);
      if (!current || new Date(item.recordedAtUtc).getTime() >= new Date(current.recordedAtUtc).getTime()) {
        aggregate.samples.set(item.metric, item);
      }
      latestByZoneMetric.set(aggregateKey, aggregate);
    }

    const items: ZoneAggregate[] = Array.from(latestByZoneMetric.values())
      .map(({ meta: displayMeta, samples }) => {
        const metrics = Object.fromEntries(
          metricKeys
            .filter((metric) => samples.get(metric))
            .map((metric) => [metric, samples.get(metric)?.value]),
        ) as Partial<Record<MetricKey, number>>;
        const metricCount = Object.keys(metrics).length;

        const latestAtLocal = Array.from(samples.values())
          .sort((left, right) => new Date(right.recordedAtUtc).getTime() - new Date(left.recordedAtUtc).getTime())[0]
          ?.recordedAtLocal ?? null;

        return {
          zone: displayMeta.rawName,
          displayName: displayMeta.displayName,
          group: displayMeta.group,
          area: displayMeta.area,
          category: resolveZoneCategory(displayMeta.displayName, displayMeta.area),
          latestAtLocal,
          metrics,
          status:
            metricCount >= 2
              ? ("正常" as const)
              : metricCount === 1
                ? ("部分采集" as const)
                : ("数据缺失" as const),
        };
      })
      .sort((left, right) => getGreenhouseDisplayMeta(left.zone).order - getGreenhouseDisplayMeta(right.zone).order);

    return NextResponse.json({ items });
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : "Failed to load greenhouse overview.",
      },
      { status: 502 },
    );
  }
}
