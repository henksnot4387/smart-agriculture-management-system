from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.repositories.settings import SettingsRepository
from app.repositories.task import TaskRepository
from app.schemas.settings import (
    SettingsProfileConfig,
    SettingsProfileItem,
    SettingsProfileListResponse,
    SettingsProfileResponse,
    SettingsProfileUpsertRequest,
    SettingsTriggerResponse,
)

DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "horticulture": {
        "title": "园艺设置",
        "description": "用于打叶、落蔓、绕头、整枝等园艺作业的自动巡检与任务触发。",
        "enabled": True,
        "config": {
            "autoCreateEnabled": False,
            "cadenceHours": 24,
            "taskTemplate": {
                "title": "园艺作业巡检任务",
                "description": "请执行打叶、绕头、落蔓检查，并回填株型一致性和异常点。",
                "priority": "MEDIUM",
                "operationType": "INSPECTION",
            },
            "rules": [],
        },
    },
    "plant_protection": {
        "title": "植保设置",
        "description": "用于打药、消毒、病害复检等植保作业的自动任务触发。",
        "enabled": True,
        "config": {
            "autoCreateEnabled": False,
            "cadenceHours": 24,
            "taskTemplate": {
                "title": "植保复检与处置任务",
                "description": "请执行病害复检、消毒或精准植保，并回填处理结果。",
                "priority": "HIGH",
                "operationType": "PLANT_PROTECTION",
            },
            "rules": [],
        },
    },
    "climate": {
        "title": "环控设置",
        "description": "用于环控策略、执行器联动和测量盒校准的自动任务触发。",
        "enabled": True,
        "config": {
            "autoCreateEnabled": False,
            "cadenceHours": 12,
            "taskTemplate": {
                "title": "环控策略复核任务",
                "description": "请检查温室环控参数与执行器状态，并回填校准结果。",
                "priority": "MEDIUM",
                "operationType": "CLIMATE_ADJUSTMENT",
            },
            "rules": [],
        },
    },
    "fertigation": {
        "title": "水肥设置",
        "description": "用于施肥机、配方、EC/pH 控制策略与灌溉执行的自动任务触发。",
        "enabled": True,
        "config": {
            "autoCreateEnabled": False,
            "cadenceHours": 8,
            "taskTemplate": {
                "title": "水肥执行与参数复核任务",
                "description": "请复核 EC/pH 控制策略、施肥机状态并回填执行数据。",
                "priority": "HIGH",
                "operationType": "FERTIGATION",
            },
            "rules": [],
        },
    },
}


class SettingsService:
    def __init__(self, *, repository: SettingsRepository, task_repository: TaskRepository):
        self._repository = repository
        self._task_repository = task_repository
        self._bootstrap_defaults()

    def list_profiles(self) -> SettingsProfileListResponse:
        rows = self._repository.list_profiles()
        return SettingsProfileListResponse(items=[self._to_item(row) for row in rows])

    def get_profile(self, *, profile_key: str) -> SettingsProfileResponse:
        row = self._repository.get_profile(profile_key=profile_key)
        if row is None:
            raise KeyError(profile_key)
        return SettingsProfileResponse(item=self._to_item(row))

    def upsert_profile(
        self,
        *,
        profile_key: str,
        payload: SettingsProfileUpsertRequest,
        updated_by_id: str,
    ) -> SettingsProfileResponse:
        if profile_key not in DEFAULT_PROFILES:
            raise KeyError(profile_key)
        default_profile = DEFAULT_PROFILES[profile_key]
        row = self._repository.upsert_profile(
            profile_key=profile_key,
            title=str(default_profile["title"]),
            description=str(default_profile["description"]),
            enabled=payload.enabled,
            config=payload.config.model_dump(mode="json"),
            updated_by_id=updated_by_id,
        )
        return SettingsProfileResponse(item=self._to_item(row))

    def trigger_profile_now(self, *, profile_key: str, actor_user_id: str) -> SettingsTriggerResponse:
        row = self._repository.get_profile(profile_key=profile_key)
        if row is None:
            raise KeyError(profile_key)
        return self._trigger_from_row(row=row, actor_user_id=actor_user_id, force=True)

    def trigger_due_profiles(self, *, actor_user_id: str) -> list[SettingsTriggerResponse]:
        responses: list[SettingsTriggerResponse] = []
        for row in self._repository.list_profiles():
            responses.append(self._trigger_from_row(row=row, actor_user_id=actor_user_id, force=False))
        return responses

    def _trigger_from_row(
        self,
        *,
        row: dict[str, Any],
        actor_user_id: str,
        force: bool,
    ) -> SettingsTriggerResponse:
        profile_key = str(row.get("profile_key") or "")
        config = SettingsProfileConfig(**(row.get("config") or {}))
        enabled = bool(row.get("enabled"))
        if not enabled:
            return SettingsTriggerResponse(profile=profile_key, triggered=False, message="配置已停用。")
        if not config.autoCreateEnabled and not force:
            return SettingsTriggerResponse(profile=profile_key, triggered=False, message="自动创建未开启。")
        if not force and row.get("last_triggered_at"):
            last_triggered = row["last_triggered_at"].astimezone(UTC)
            if datetime.now(UTC) - last_triggered < timedelta(hours=config.cadenceHours):
                return SettingsTriggerResponse(profile=profile_key, triggered=False, message="未到触发周期。")

        template = config.taskTemplate
        metadata = {
            "automationProfile": profile_key,
            "automationTriggeredAt": datetime.now(UTC).isoformat(),
            "operationType": template.operationType,
            "rules": config.rules,
        }
        task_row = self._task_repository.create_system_task(
            title=template.title,
            description=template.description,
            priority=template.priority,
            source="EXTERNAL",
            created_by_id=actor_user_id,
            due_at=datetime.now(UTC) + timedelta(hours=config.cadenceHours),
            metadata=metadata,
        )
        task_id = str(task_row["id"])
        self._repository.mark_triggered(profile_key=profile_key, task_id=task_id)
        return SettingsTriggerResponse(
            profile=profile_key,
            triggered=True,
            taskId=task_id,
            message="已创建自动触发任务。",
        )

    def _bootstrap_defaults(self) -> None:
        existing = {str(row.get("profile_key") or "") for row in self._repository.list_profiles()}
        bootstrap_user_id = self._task_repository.get_first_management_user_id()
        if not bootstrap_user_id:
            return
        for profile_key, profile in DEFAULT_PROFILES.items():
            if profile_key in existing:
                continue
            self._repository.upsert_profile(
                profile_key=profile_key,
                title=str(profile["title"]),
                description=str(profile["description"]),
                enabled=bool(profile["enabled"]),
                config=dict(profile["config"]),
                updated_by_id=bootstrap_user_id,
            )

    def _to_item(self, row: dict[str, Any]) -> SettingsProfileItem:
        return SettingsProfileItem(
            profile=str(row.get("profile_key") or ""),
            title=str(row.get("title") or ""),
            description=str(row.get("description") or ""),
            enabled=bool(row.get("enabled")),
            config=SettingsProfileConfig(**(row.get("config") or {})),
            updatedAt=row.get("updated_at"),
            updatedById=str(row.get("updated_by_id") or "") or None,
            lastTriggeredAt=row.get("last_triggered_at"),
            lastTaskId=str(row.get("last_task_id") or "") or None,
        )
