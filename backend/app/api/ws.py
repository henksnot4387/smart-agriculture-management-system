from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.ai.vision.dependencies import get_vision_event_hub, get_vision_task_service
from app.ai.vision.events import VisionTaskEventHub
from app.ai.vision.service import VisionTaskService
from app.core.config import settings

router = APIRouter(
    prefix="/api/ws",
    tags=["ws"],
)


def _is_ws_token_valid(websocket: WebSocket) -> bool:
    configured_token = settings.backend_api_token.strip()
    if not configured_token:
        return settings.app_env.lower() not in {"production", "prod"}
    request_token = (websocket.query_params.get("token") or "").strip()
    return request_token == configured_token


@router.websocket("/vision/tasks")
async def vision_tasks_stream(
    websocket: WebSocket,
    event_hub: VisionTaskEventHub = Depends(get_vision_event_hub),
    vision_service: VisionTaskService = Depends(get_vision_task_service),
) -> None:
    if not _is_ws_token_valid(websocket):
        await websocket.close(code=4401, reason="Invalid API token.")
        return

    await event_hub.register(websocket)
    try:
        await websocket.send_json(
            {
                "type": "vision.connected",
                "connectedAt": datetime.now(UTC).isoformat(),
                "queueDepth": await vision_service.get_queue_depth(),
                "runtime": (await vision_service.get_runtime()).model_dump(mode="json"),
            }
        )

        while True:
            incoming = await websocket.receive_text()
            if incoming.strip().lower() == "ping":
                await websocket.send_json(
                    {
                        "type": "vision.pong",
                        "at": datetime.now(UTC).isoformat(),
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        await event_hub.unregister(websocket)
