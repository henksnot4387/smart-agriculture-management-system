from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.security import require_api_token
from app.core.config import settings
from app.repositories.task import TaskRepository
from app.schemas.task import (
    ApproveTaskRequest,
    AssignedToFilter,
    CompleteTaskRequest,
    TaskAssigneeListResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskSource,
    TaskStatus,
    TaskTransitionResponse,
)
from app.services.task import TaskService, TaskServiceError

router = APIRouter(
    prefix="/api/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_api_token)],
)


def get_task_service() -> TaskService:
    return TaskService(TaskRepository(settings))


def require_user_role(x_user_role: str | None = Header(default=None, alias="X-User-Role")) -> str:
    role = (x_user_role or "").strip().upper()
    if not role:
        raise HTTPException(status_code=401, detail="Missing X-User-Role header.")
    return role


def require_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header.")
    return user_id


def _handle_service_error(exc: TaskServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("", response_model=TaskListResponse)
def list_tasks(
    status: TaskStatus | None = None,
    source: TaskSource | None = None,
    assignedTo: AssignedToFilter = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    try:
        return service.list_tasks(
            role=role,
            user_id=user_id,
            limit=limit,
            status=status,
            source=source,
            assigned_to=assignedTo,
        )
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.get("/assignees", response_model=TaskAssigneeListResponse)
def list_task_assignees(
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskAssigneeListResponse:
    try:
        return service.list_assignees(role=role, user_id=user_id)
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task_detail(
    task_id: str,
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskDetailResponse:
    try:
        return service.get_task_detail(role=role, user_id=user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.post("/{task_id}/approve", response_model=TaskTransitionResponse)
def approve_task(
    task_id: str,
    payload: ApproveTaskRequest,
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskTransitionResponse:
    try:
        return service.approve_task(
            role=role,
            user_id=user_id,
            task_id=task_id,
            payload=payload,
        )
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.post("/{task_id}/claim", response_model=TaskTransitionResponse)
def claim_task(
    task_id: str,
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskTransitionResponse:
    try:
        return service.claim_task(role=role, user_id=user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.post("/{task_id}/start", response_model=TaskTransitionResponse)
def start_task(
    task_id: str,
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskTransitionResponse:
    try:
        return service.start_task(role=role, user_id=user_id, task_id=task_id)
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.post("/{task_id}/complete", response_model=TaskTransitionResponse)
def complete_task(
    task_id: str,
    payload: CompleteTaskRequest,
    role: str = Depends(require_user_role),
    user_id: str = Depends(require_user_id),
    service: TaskService = Depends(get_task_service),
) -> TaskTransitionResponse:
    try:
        return service.complete_task(
            role=role,
            user_id=user_id,
            task_id=task_id,
            payload=payload,
        )
    except TaskServiceError as exc:
        raise _handle_service_error(exc) from exc
