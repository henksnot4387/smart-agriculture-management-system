import type {
  SettingsProfileKey,
  SettingsProfileListPayload,
  SettingsProfilePayload,
  SettingsTriggerPayload,
} from "@/src/types/settings";

export class SettingsApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SettingsApiError";
    this.status = status;
  }
}

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let message = fallback;
    try {
      const payload = (await response.json()) as { detail?: string; error?: string };
      message = payload.detail || payload.error || fallback;
    } catch {
      // ignore
    }
    throw new SettingsApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchSettingsProfiles(): Promise<SettingsProfileListPayload> {
  const response = await fetch("/api/settings", { cache: "no-store", credentials: "include" });
  return readJson<SettingsProfileListPayload>(response, "加载设置列表失败。");
}

export async function fetchSettingsProfile(profile: SettingsProfileKey): Promise<SettingsProfilePayload> {
  const response = await fetch(`/api/settings/${profile}`, { cache: "no-store", credentials: "include" });
  return readJson<SettingsProfilePayload>(response, "加载设置详情失败。");
}

export async function updateSettingsProfile(
  profile: SettingsProfileKey,
  payload: {
    enabled: boolean;
    config: {
      autoCreateEnabled: boolean;
      cadenceHours: number;
      taskTemplate: {
        title: string;
        description: string;
        priority: "LOW" | "MEDIUM" | "HIGH";
        operationType: string;
      };
      rules: Array<Record<string, unknown>>;
    };
  },
): Promise<SettingsProfilePayload> {
  const response = await fetch(`/api/settings/${profile}`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<SettingsProfilePayload>(response, "保存设置失败。");
}

export async function triggerSettingsProfile(profile: SettingsProfileKey): Promise<SettingsTriggerPayload> {
  const response = await fetch(`/api/settings/${profile}/trigger`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: { "content-type": "application/json" },
  });
  return readJson<SettingsTriggerPayload>(response, "触发自动任务失败。");
}
