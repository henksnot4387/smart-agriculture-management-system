from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.integrations.hoogendoorn.exceptions import (
    ConfigurationHoogendoornError,
    TemporaryHoogendoornError,
)

logger = logging.getLogger("app.middleware.exception")


def _request_extra(request: Request, request_id: str, error_code: str) -> dict[str, object]:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    return {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "route": route_path or request.url.path,
        "user_id": request.headers.get("x-user-id"),
        "user_role": (request.headers.get("x-user-role") or "").upper() or None,
        "error_code": error_code,
    }


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except TemporaryHoogendoornError as exc:
            request_id = getattr(request.state, "request_id", str(uuid4()))
            request.state.error_code = "HOOGENDOORN_TEMPORARY_FAILURE"
            logger.warning(
                "Retry budget exhausted for Hoogendoorn request",
                extra=_request_extra(request, request_id, "HOOGENDOORN_TEMPORARY_FAILURE"),
            )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": str(exc),
                    "error_code": "HOOGENDOORN_TEMPORARY_FAILURE",
                    "request_id": request_id,
                },
            )
        except ConfigurationHoogendoornError as exc:
            request_id = getattr(request.state, "request_id", str(uuid4()))
            request.state.error_code = "HOOGENDOORN_CONFIG_ERROR"
            logger.error(
                "Invalid Hoogendoorn configuration",
                extra=_request_extra(request, request_id, "HOOGENDOORN_CONFIG_ERROR"),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(exc),
                    "error_code": "HOOGENDOORN_CONFIG_ERROR",
                    "request_id": request_id,
                },
            )
        except Exception:
            request_id = getattr(request.state, "request_id", str(uuid4()))
            request.state.error_code = "UNHANDLED_EXCEPTION"
            logger.exception(
                "Unhandled application error",
                extra=_request_extra(request, request_id, "UNHANDLED_EXCEPTION"),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal Server Error",
                    "error_code": "UNHANDLED_EXCEPTION",
                    "request_id": request_id,
                },
            )
