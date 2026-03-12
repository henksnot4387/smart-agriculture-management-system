from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.repositories.task import TaskRepository
from app.schemas.task import (
    ApproveTaskRequest,
    CompleteTaskRequest,
    TaskAssigneeListResponse,
    TaskAssigneeOption,
    TaskDetailResponse,
    TaskItem,
    TaskListResponse,
    TaskTransitionResponse,
)

MANAGEMENT_ROLES = {"SUPER_ADMIN", "ADMIN", "EXPERT"}
ALL_ROLES = MANAGEMENT_ROLES | {"WORKER"}


class TaskServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class TaskService:
    def __init__(self, repository: TaskRepository):
        self._repository = repository

    def list_tasks(
        self,
        *,
        role: str,
        user_id: str,
        limit: int,
        status: str | None,
        source: str | None,
        assigned_to: str,
    ) -> TaskListResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        worker_scope = normalized_role == "WORKER"
        if worker_scope and assigned_to not in {"me", "unassigned", "all"}:
            raise TaskServiceError("Invalid assignedTo filter for worker.", status_code=422)

        total, rows = self._repository.list_tasks(
            limit=limit,
            status=status,
            source=source,
            assigned_to=assigned_to,
            user_id=user_id,
            worker_scope=worker_scope,
        )
        items = [self._to_item(row) for row in rows]
        return TaskListResponse(total=total, limit=limit, items=items)

    def get_task_detail(self, *, role: str, user_id: str, task_id: str) -> TaskDetailResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        row = self._repository.get_task_by_id(task_id=task_id)
        if not row:
            raise TaskServiceError("Task not found.", status_code=404)

        if normalized_role == "WORKER":
            assignee_id = row.get("assignee_id")
            is_approved_unassigned = row.get("status") == "APPROVED" and assignee_id is None
            if assignee_id != user_id and not is_approved_unassigned:
                raise TaskServiceError("Worker cannot access this task.", status_code=403)

        return TaskDetailResponse(task=self._to_item(row))

    def list_assignees(self, *, role: str, user_id: str) -> TaskAssigneeListResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        if normalized_role not in MANAGEMENT_ROLES:
            raise TaskServiceError("Only management roles can list assignees.", status_code=403)
        rows = self._repository.list_worker_assignees()
        return TaskAssigneeListResponse(
            items=[
                TaskAssigneeOption(
                    id=str(row["id"]),
                    email=str(row["email"]),
                    name=row.get("name"),
                    role=str(row.get("role") or "WORKER"),
                )
                for row in rows
            ]
        )

    def approve_task(
        self,
        *,
        role: str,
        user_id: str,
        task_id: str,
        payload: ApproveTaskRequest,
    ) -> TaskTransitionResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        if normalized_role not in MANAGEMENT_ROLES:
            raise TaskServiceError("Only management roles can approve tasks.", status_code=403)

        if payload.assigneeId:
            assignee = self._repository.get_active_user(user_id=payload.assigneeId)
            if not assignee or not assignee.get("is_active"):
                raise TaskServiceError("Assignee user not found or inactive.", status_code=404)
            if str(assignee.get("role") or "").upper() != "WORKER":
                raise TaskServiceError("Assignee must be a WORKER user.", status_code=422)

        row = self._repository.approve_task(
            task_id=task_id,
            approved_by_id=user_id,
            assignee_id=payload.assigneeId,
        )
        if not row:
            existing = self._repository.get_task_by_id(task_id=task_id)
            if not existing:
                raise TaskServiceError("Task not found.", status_code=404)
            raise TaskServiceError("Only PENDING task can be approved.", status_code=409)
        return TaskTransitionResponse(message="Task approved.", task=self._to_item(row))

    def claim_task(self, *, role: str, user_id: str, task_id: str) -> TaskTransitionResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        if normalized_role != "WORKER":
            raise TaskServiceError("Only WORKER can claim task.", status_code=403)

        row = self._repository.claim_task(task_id=task_id, user_id=user_id)
        if row:
            return TaskTransitionResponse(message="Task claimed.", task=self._to_item(row))

        existing = self._repository.get_task_by_id(task_id=task_id)
        if not existing:
            raise TaskServiceError("Task not found.", status_code=404)
        if existing.get("status") != "APPROVED":
            raise TaskServiceError("Only APPROVED task can be claimed.", status_code=409)
        if existing.get("assignee_id") == user_id:
            return TaskTransitionResponse(message="Task already assigned to current worker.", task=self._to_item(existing))
        raise TaskServiceError("Task already claimed by another worker.", status_code=409)

    def start_task(self, *, role: str, user_id: str, task_id: str) -> TaskTransitionResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        if normalized_role != "WORKER":
            raise TaskServiceError("Only WORKER can start task.", status_code=403)

        row = self._repository.start_task(task_id=task_id, user_id=user_id)
        if row:
            return TaskTransitionResponse(message="Task started.", task=self._to_item(row))

        existing = self._repository.get_task_by_id(task_id=task_id)
        if not existing:
            raise TaskServiceError("Task not found.", status_code=404)
        if existing.get("assignee_id") != user_id:
            raise TaskServiceError("Task is not assigned to current worker.", status_code=403)
        raise TaskServiceError("Only APPROVED task can transition to IN_PROGRESS.", status_code=409)

    def complete_task(
        self,
        *,
        role: str,
        user_id: str,
        task_id: str,
        payload: CompleteTaskRequest,
    ) -> TaskTransitionResponse:
        normalized_role = self._validate_role(role)
        self._assert_actor(role=normalized_role, user_id=user_id)
        if normalized_role != "WORKER":
            raise TaskServiceError("Only WORKER can complete task.", status_code=403)

        report = payload.model_dump(mode="json")
        report["completedById"] = user_id
        report["completedAt"] = datetime.now(UTC).isoformat()

        row = self._repository.complete_task(
            task_id=task_id,
            user_id=user_id,
            execution_report=report,
        )
        if row:
            return TaskTransitionResponse(message="Task completed.", task=self._to_item(row))

        existing = self._repository.get_task_by_id(task_id=task_id)
        if not existing:
            raise TaskServiceError("Task not found.", status_code=404)
        if existing.get("assignee_id") != user_id:
            raise TaskServiceError("Task is not assigned to current worker.", status_code=403)
        raise TaskServiceError("Only IN_PROGRESS task can transition to COMPLETED.", status_code=409)

    def _validate_role(self, role: str) -> str:
        normalized = (role or "").strip().upper()
        if normalized not in ALL_ROLES:
            raise TaskServiceError("Invalid user role.", status_code=403)
        return normalized

    def _assert_actor(self, *, role: str, user_id: str) -> None:
        actor = self._repository.get_active_user(user_id=user_id)
        if not actor:
            raise TaskServiceError("User not found.", status_code=401)
        if not bool(actor.get("is_active")):
            raise TaskServiceError("User is inactive.", status_code=403)
        db_role = str(actor.get("role") or "").upper()
        if db_role != role:
            raise TaskServiceError("User role mismatch.", status_code=403)

    def _to_item(self, row: dict[str, Any]) -> TaskItem:
        metadata = row.get("metadata")
        return TaskItem(
            taskId=str(row["id"]),
            title=str(row.get("title") or ""),
            description=row.get("description"),
            status=str(row.get("status") or "PENDING"),
            priority=str(row.get("priority") or "MEDIUM"),
            source=str(row.get("source") or "AI"),
            metadata=metadata if isinstance(metadata, dict) else {},
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            approvedAt=row.get("approved_at"),
            startedAt=row.get("started_at"),
            completedAt=row.get("completed_at"),
            dueAt=row.get("due_at"),
            createdById=str(row.get("created_by_id") or ""),
            createdByEmail=row.get("created_by_email"),
            assigneeId=row.get("assignee_id"),
            assigneeEmail=row.get("assignee_email"),
            approvedById=row.get("approved_by_id"),
            approvedByEmail=row.get("approved_by_email"),
        )
