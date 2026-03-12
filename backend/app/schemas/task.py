from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


TaskStatus = Literal["PENDING", "APPROVED", "IN_PROGRESS", "COMPLETED"]
TaskPriority = Literal["LOW", "MEDIUM", "HIGH"]
TaskSource = Literal["AI", "MANUAL", "EXTERNAL"]
AssignedToFilter = Literal["me", "unassigned", "all"]
OperationType = Literal[
    "IRRIGATION",
    "FERTIGATION",
    "PLANT_PROTECTION",
    "CLIMATE_ADJUSTMENT",
    "INSPECTION",
    "OTHER",
]


class TaskAssigneeOption(BaseModel):
    id: str
    email: str
    name: str | None = None
    role: str


class TaskAssigneeListResponse(BaseModel):
    items: list[TaskAssigneeOption]


class TaskItem(BaseModel):
    taskId: str
    title: str
    description: str | None = None
    status: TaskStatus
    priority: TaskPriority
    source: TaskSource
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime
    updatedAt: datetime
    approvedAt: datetime | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    dueAt: datetime | None = None
    createdById: str
    createdByEmail: str | None = None
    assigneeId: str | None = None
    assigneeEmail: str | None = None
    approvedById: str | None = None
    approvedByEmail: str | None = None


class TaskListResponse(BaseModel):
    total: int
    limit: int
    items: list[TaskItem]


class TaskDetailResponse(BaseModel):
    task: TaskItem


class TaskTransitionResponse(BaseModel):
    message: str
    task: TaskItem


class ApproveTaskRequest(BaseModel):
    assigneeId: str | None = None


class SensorReading(BaseModel):
    temperature: float | None = None
    humidity: float | None = None
    ec: float | None = None
    ph: float | None = None


class ExecutionMaterial(BaseModel):
    name: str
    amount: float
    unit: str

    @field_validator("name", "unit")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized


class CompleteTaskRequest(BaseModel):
    operationType: OperationType
    executedActions: list[str] = Field(default_factory=list)
    readingsBefore: SensorReading | None = None
    readingsAfter: SensorReading | None = None
    materials: list[ExecutionMaterial] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    resultSummary: str
    attachments: list[str] = Field(default_factory=list)

    @field_validator("executedActions")
    @classmethod
    def _validate_actions(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item and item.strip()]
        if not normalized:
            raise ValueError("executedActions must include at least one action")
        return normalized

    @field_validator("anomalies", "attachments")
    @classmethod
    def _normalize_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @field_validator("resultSummary")
    @classmethod
    def _validate_result_summary(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("resultSummary must be at least 8 characters")
        return normalized
