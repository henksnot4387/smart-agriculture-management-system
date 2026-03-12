from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class VisionTaskEventHub:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def publish(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)
        if not targets:
            return

        disconnected: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)

        if disconnected:
            async with self._lock:
                for websocket in disconnected:
                    self._connections.discard(websocket)

    async def connection_count(self) -> int:
        async with self._lock:
            return len(self._connections)

    async def close_all(self, code: int = 1001, reason: str = "Server shutdown") -> None:
        async with self._lock:
            targets = list(self._connections)
            self._connections.clear()
        for websocket in targets:
            try:
                await websocket.close(code=code, reason=reason)
            except Exception:
                pass
