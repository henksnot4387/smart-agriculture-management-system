import type { DashboardRange, SensorDashboardPayload } from "@/src/types/sensor";

type FetchDashboardOptions = {
  range: DashboardRange;
  zone?: string;
  signal?: AbortSignal;
};

export async function fetchDashboardData({
  range,
  zone,
  signal,
}: FetchDashboardOptions): Promise<SensorDashboardPayload> {
  const params = new URLSearchParams({ range });
  if (zone) {
    params.set("zone", zone);
  }

  const response = await fetch(`/api/dashboard/sensor?${params.toString()}`, {
    method: "GET",
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    let message = "Failed to load dashboard data.";
    try {
      const payload = (await response.json()) as { detail?: string; error?: string };
      message = payload.detail || payload.error || message;
    } catch {
      // Ignore JSON parse failures and fall back to the default message.
    }
    throw new Error(message);
  }

  return (await response.json()) as SensorDashboardPayload;
}
