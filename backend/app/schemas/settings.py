from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SettingsProfileKey = Literal["horticulture", "plant_protection", "climate", "fertigation"]


class SettingsTaskTemplate(BaseModel):
    title: str
    description: str
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    operationType: str = "INSPECTION"


class SettingsProfileConfig(BaseModel):
    autoCreateEnabled: bool = False
    cadenceHours: int = Field(default=24, ge=1, le=168)
    taskTemplate: SettingsTaskTemplate
    rules: list[dict[str, Any]] = Field(default_factory=list)


class SettingsProfileItem(BaseModel):
    profile: SettingsProfileKey
    title: str
    description: str
    enabled: bool
    config: SettingsProfileConfig
    updatedAt: datetime | None = None
    updatedById: str | None = None
    lastTriggeredAt: datetime | None = None
    lastTaskId: str | None = None


class SettingsProfileResponse(BaseModel):
    item: SettingsProfileItem


class SettingsProfileListResponse(BaseModel):
    items: list[SettingsProfileItem]


class SettingsProfileUpsertRequest(BaseModel):
    enabled: bool = True
    config: SettingsProfileConfig


class SettingsTriggerResponse(BaseModel):
    profile: SettingsProfileKey
    triggered: bool
    taskId: str | None = None
    message: str
