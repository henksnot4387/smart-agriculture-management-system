from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth_context import ActorContext, require_roles
from app.core.config import settings
from app.core.security import require_api_token
from app.repositories.settings import SettingsRepository
from app.repositories.task import TaskRepository
from app.schemas.settings import (
    SettingsProfileListResponse,
    SettingsProfileResponse,
    SettingsProfileUpsertRequest,
    SettingsTriggerResponse,
)
from app.services.settings import SettingsService

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_api_token)],
)

require_settings_manager = require_roles({"SUPER_ADMIN", "ADMIN"})


@lru_cache
def get_settings_service() -> SettingsService:
    return SettingsService(
        repository=SettingsRepository(settings),
        task_repository=TaskRepository(settings),
    )


@router.get("", response_model=SettingsProfileListResponse)
def list_settings_profiles(
    _: ActorContext = Depends(require_settings_manager),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsProfileListResponse:
    return service.list_profiles()


@router.get("/{profile_key}", response_model=SettingsProfileResponse)
def get_settings_profile(
    profile_key: str,
    _: ActorContext = Depends(require_settings_manager),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsProfileResponse:
    try:
        return service.get_profile(profile_key=profile_key)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.") from exc


@router.post("/{profile_key}", response_model=SettingsProfileResponse)
def upsert_settings_profile(
    profile_key: str,
    payload: SettingsProfileUpsertRequest,
    actor: ActorContext = Depends(require_settings_manager),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsProfileResponse:
    try:
        return service.upsert_profile(
            profile_key=profile_key,
            payload=payload,
            updated_by_id=actor.user_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.") from exc


@router.post("/{profile_key}/trigger", response_model=SettingsTriggerResponse)
def trigger_settings_profile(
    profile_key: str,
    actor: ActorContext = Depends(require_settings_manager),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsTriggerResponse:
    try:
        return service.trigger_profile_now(profile_key=profile_key, actor_user_id=actor.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.") from exc
