from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.repositories.observability import ObservabilityRepository


class ObservabilityService:
    def __init__(self, repository: ObservabilityRepository):
        self._repository = repository

    def bootstrap(self) -> None:
        self._repository.ensure_schema()

    def record_http_event(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        route: str,
        domain: str,
        status_code: int,
        latency_ms: float,
        error_code: str | None,
        user_id: str | None,
        user_role: str | None,
    ) -> None:
        slow_threshold = max(1, int(settings.slow_request_threshold_ms))
        self._repository.insert_http_event(
            request_id=request_id,
            method=method,
            path=path,
            route=route,
            domain=domain,
            status_code=status_code,
            latency_ms=latency_ms,
            is_slow=latency_ms >= slow_threshold,
            error_code=error_code,
            user_id=user_id,
            user_role=user_role,
        )

    def get_overview(self, *, window_hours: int) -> dict:
        slow_threshold = max(1, int(settings.slow_request_threshold_ms))
        base = self._repository.get_overview_metrics(
            window_hours=window_hours,
            slow_threshold_ms=slow_threshold,
        )
        return {
            "window_hours": window_hours,
            "slow_threshold_ms": slow_threshold,
            "total_requests": int(base.get("total_requests", 0)),
            "error_requests": int(base.get("error_requests", 0)),
            "slow_requests": int(base.get("slow_requests", 0)),
            "p95_latency_ms": round(float(base.get("p95_latency_ms", 0.0) or 0.0), 2),
            "top_routes": self._repository.list_route_metrics(
                window_hours=window_hours,
                slow_threshold_ms=slow_threshold,
                limit=10,
            ),
            "domain_stats": self._repository.list_domain_metrics(
                window_hours=window_hours,
                slow_threshold_ms=slow_threshold,
            ),
            "error_code_stats": self._repository.list_error_code_metrics(
                window_hours=window_hours,
                limit=10,
            ),
            "task_failures": self._repository.list_task_failures(
                window_hours=window_hours,
                limit=10,
            ),
        }

    def list_recent_errors(self, *, window_hours: int, limit: int) -> dict:
        return {
            "window_hours": window_hours,
            "items": self._repository.list_recent_errors(window_hours=window_hours, limit=limit),
        }

    def list_recent_slow_requests(self, *, window_hours: int, limit: int) -> dict:
        slow_threshold = max(1, int(settings.slow_request_threshold_ms))
        return {
            "window_hours": window_hours,
            "slow_threshold_ms": slow_threshold,
            "items": self._repository.list_recent_slow_requests(
                window_hours=window_hours,
                slow_threshold_ms=slow_threshold,
                limit=limit,
            ),
        }

    def list_task_failures(self, *, window_hours: int, limit: int) -> dict:
        return {
            "window_hours": window_hours,
            "items": self._repository.list_task_failures(window_hours=window_hours, limit=limit),
        }


@lru_cache
def get_observability_service() -> ObservabilityService:
    service = ObservabilityService(repository=ObservabilityRepository(settings))
    service.bootstrap()
    return service
