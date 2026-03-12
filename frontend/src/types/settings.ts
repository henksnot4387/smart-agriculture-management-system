export type SettingsProfileKey = "horticulture" | "plant_protection" | "climate" | "fertigation";

export type SettingsProfileConfig = {
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

export type SettingsProfileItem = {
  profile: SettingsProfileKey;
  title: string;
  description: string;
  enabled: boolean;
  config: SettingsProfileConfig;
  updatedAt?: string | null;
  updatedById?: string | null;
  lastTriggeredAt?: string | null;
  lastTaskId?: string | null;
};

export type SettingsProfileListPayload = {
  items: SettingsProfileItem[];
};

export type SettingsProfilePayload = {
  item: SettingsProfileItem;
};

export type SettingsTriggerPayload = {
  profile: SettingsProfileKey;
  triggered: boolean;
  taskId?: string | null;
  message: string;
};
