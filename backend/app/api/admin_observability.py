from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.auth_context import ActorContext, require_roles
from app.core.security import require_api_token
from app.schemas.observability import (
    ObservabilityDomainMetric,
    ObservabilityErrorCodeMetric,
    ObservabilityErrorEvent,
    ObservabilityErrorsResponse,
    ObservabilityOverviewResponse,
    ObservabilityRouteMetric,
    ObservabilitySlowRequestsResponse,
    ObservabilityTaskFailureMetric,
    ObservabilityTaskFailuresResponse,
)
from app.services.observability import ObservabilityService, get_observability_service

router = APIRouter(
    prefix="/api/admin/observability",
    tags=["admin-observability"],
    dependencies=[Depends(require_api_token)],
)

require_super_admin = require_roles({"SUPER_ADMIN"})


@router.get("/overview", response_model=ObservabilityOverviewResponse)
def observability_overview(
    _: ActorContext = Depends(require_super_admin),
    hours: int = Query(default=24, ge=1, le=168),
    service: ObservabilityService = Depends(get_observability_service),
) -> ObservabilityOverviewResponse:
    payload = service.get_overview(window_hours=hours)
    return ObservabilityOverviewResponse(
        windowHours=int(payload["window_hours"]),
        slowThresholdMs=int(payload["slow_threshold_ms"]),
        totalRequests=int(payload["total_requests"]),
        errorRequests=int(payload["error_requests"]),
        slowRequests=int(payload["slow_requests"]),
        p95LatencyMs=float(payload["p95_latency_ms"]),
        topRoutes=[
            ObservabilityRouteMetric(
                route=str(item.get("route") or ""),
                requestCount=int(item.get("request_count") or 0),
                errorCount=int(item.get("error_count") or 0),
                slowCount=int(item.get("slow_count") or 0),
                avgLatencyMs=round(float(item.get("avg_latency_ms") or 0.0), 2),
                p95LatencyMs=round(float(item.get("p95_latency_ms") or 0.0), 2),
                maxLatencyMs=round(float(item.get("max_latency_ms") or 0.0), 2),
            )
            for item in payload.get("top_routes", [])
        ],
        domainStats=[
            ObservabilityDomainMetric(
                domain=str(item.get("domain") or "unknown"),
                requestCount=int(item.get("request_count") or 0),
                errorCount=int(item.get("error_count") or 0),
                slowCount=int(item.get("slow_count") or 0),
            )
            for item in payload.get("domain_stats", [])
        ],
        errorCodeStats=[
            ObservabilityErrorCodeMetric(
                errorCode=str(item.get("error_code") or "UNKNOWN"),
                count=int(item.get("count") or 0),
            )
            for item in payload.get("error_code_stats", [])
        ],
        taskFailures=[
            ObservabilityTaskFailureMetric(
                jobId=str(item.get("job_id") or ""),
                failedCount=int(item.get("failed_count") or 0),
                lastFailedAt=item.get("last_failed_at"),
                lastError=item.get("last_error"),
            )
            for item in payload.get("task_failures", [])
        ],
    )


@router.get("/errors", response_model=ObservabilityErrorsResponse)
def list_observability_errors(
    _: ActorContext = Depends(require_super_admin),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    service: ObservabilityService = Depends(get_observability_service),
) -> ObservabilityErrorsResponse:
    payload = service.list_recent_errors(window_hours=hours, limit=limit)
    return ObservabilityErrorsResponse(
        windowHours=int(payload["window_hours"]),
        items=[
            ObservabilityErrorEvent(
                requestId=str(item.get("request_id") or ""),
                method=str(item.get("method") or ""),
                path=str(item.get("path") or ""),
                route=str(item.get("route") or ""),
                statusCode=int(item.get("status_code") or 0),
                durationMs=round(float(item.get("latency_ms") or 0.0), 2),
                errorCode=item.get("error_code"),
                userId=item.get("user_id"),
                userRole=item.get("user_role"),
                occurredAt=item["occurred_at"],
            )
            for item in payload.get("items", [])
        ],
    )


@router.get("/slow-requests", response_model=ObservabilitySlowRequestsResponse)
def list_observability_slow_requests(
    _: ActorContext = Depends(require_super_admin),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    service: ObservabilityService = Depends(get_observability_service),
) -> ObservabilitySlowRequestsResponse:
    payload = service.list_recent_slow_requests(window_hours=hours, limit=limit)
    return ObservabilitySlowRequestsResponse(
        windowHours=int(payload["window_hours"]),
        slowThresholdMs=int(payload["slow_threshold_ms"]),
        items=[
            ObservabilityErrorEvent(
                requestId=str(item.get("request_id") or ""),
                method=str(item.get("method") or ""),
                path=str(item.get("path") or ""),
                route=str(item.get("route") or ""),
                statusCode=int(item.get("status_code") or 0),
                durationMs=round(float(item.get("latency_ms") or 0.0), 2),
                errorCode=item.get("error_code"),
                userId=item.get("user_id"),
                userRole=item.get("user_role"),
                occurredAt=item["occurred_at"],
            )
            for item in payload.get("items", [])
        ],
    )


@router.get("/task-failures", response_model=ObservabilityTaskFailuresResponse)
def list_observability_task_failures(
    _: ActorContext = Depends(require_super_admin),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=20, ge=1, le=200),
    service: ObservabilityService = Depends(get_observability_service),
) -> ObservabilityTaskFailuresResponse:
    payload = service.list_task_failures(window_hours=hours, limit=limit)
    return ObservabilityTaskFailuresResponse(
        windowHours=int(payload["window_hours"]),
        items=[
            ObservabilityTaskFailureMetric(
                jobId=str(item.get("job_id") or ""),
                failedCount=int(item.get("failed_count") or 0),
                lastFailedAt=item.get("last_failed_at"),
                lastError=item.get("last_error"),
            )
            for item in payload.get("items", [])
        ],
    )
