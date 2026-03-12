from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.services.observability import get_observability_service

logger = logging.getLogger("app.middleware.request")
SLOW_THRESHOLD_MS = max(1, int(settings.slow_request_threshold_ms))
MAX_DEBUG_SLEEP_MS = 5000


def _normalize_error_code(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    if not normalized:
        return None
    return normalized[:96]


def _extract_error_code(response) -> str | None:
    content_type = str(response.headers.get("content-type", "")).lower()
    if "application/json" not in content_type:
        return None

    body = getattr(response, "body", None)
    if not body:
        return None
    if isinstance(body, memoryview):
        body = body.tobytes()
    if isinstance(body, str):
        body = body.encode("utf-8")
    if not isinstance(body, (bytes, bytearray)):
        return None

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None

    if not isinstance(payload, dict):
        return None

    candidate = payload.get("error_code") or payload.get("code")
    if candidate is None and "detail" in payload:
        detail = payload.get("detail")
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                candidate = first.get("type") or first.get("msg")
            else:
                candidate = first
        else:
            candidate = detail
    return _normalize_error_code(candidate)


def _resolve_route(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return str(route_path)
    return str(request.url.path)


def _resolve_domain(route: str) -> str:
    if route.startswith("/api/sensor") or route.startswith("/integrations/hoogendoorn"):
        return "sensor"
    if route.startswith("/api/vision") or route.startswith("/api/ws/vision"):
        return "vision"
    if route.startswith("/api/ai-insights") or route.startswith("/api/copilot"):
        return "ai-insights"
    if route.startswith("/api/admin/scheduler"):
        return "scheduler"
    if route.startswith("/api/tasks"):
        return "tasks"
    if route.startswith("/api/admin/observability"):
        return "observability"
    return "system"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        request.state.request_id = request_id

        started_at = time.perf_counter()

        # Dev-only hook used by verification scripts to generate deterministic slow requests.
        debug_sleep_ms_raw = str(request.headers.get("x-debug-sleep-ms", "")).strip()
        if settings.app_env != "production" and debug_sleep_ms_raw:
            try:
                debug_sleep_ms = max(0, int(debug_sleep_ms_raw))
            except ValueError:
                debug_sleep_ms = 0
            if debug_sleep_ms > 0:
                await asyncio.sleep(min(debug_sleep_ms, MAX_DEBUG_SLEEP_MS) / 1000)

        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        route = _resolve_route(request)
        domain = _resolve_domain(route)
        user_id = str(request.headers.get("x-user-id", "")).strip() or None
        user_role = str(request.headers.get("x-user-role", "")).strip().upper() or None
        error_code = getattr(request.state, "error_code", None)
        if not error_code:
            error_code = _extract_error_code(response)
        if response.status_code >= 400 and not error_code:
            error_code = f"HTTP_{response.status_code}"
        is_slow = elapsed_ms >= SLOW_THRESHOLD_MS

        response.headers["X-Request-ID"] = request_id
        if is_slow:
            response.headers["X-Slow-Request"] = "1"

        log_payload = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "route": route,
            "domain": domain,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
            "slow_request": is_slow,
            "error_code": error_code,
            "user_id": user_id,
            "user_role": user_role,
        }

        if is_slow:
            logger.warning("Slow request detected", extra=log_payload)

        logger.info(
            "Handled request",
            extra=log_payload,
        )

        try:
            get_observability_service().record_http_event(
                request_id=request_id,
                method=request.method,
                path=str(request.url.path),
                route=route,
                domain=domain,
                status_code=int(response.status_code),
                latency_ms=float(elapsed_ms),
                error_code=error_code,
                user_id=user_id,
                user_role=user_role,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to persist observability event",
                extra={"request_id": request_id, "error_code": "OBSERVABILITY_WRITE_FAILED", "error": str(exc)},
            )
        return response
