from __future__ import annotations

import asyncio
import logging

from app.ai.vision.service import VisionTaskService

logger = logging.getLogger("app.workers.vision")


class VisionQueueWorker:
    def __init__(self, service: VisionTaskService):
        self._service = service
        self._stop_event = asyncio.Event()

    async def run_forever(self) -> None:
        logger.info("Vision queue worker started")
        while not self._stop_event.is_set():
            try:
                await self._service.process_next_task(timeout_seconds=1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Vision queue worker cycle failed")
                await asyncio.sleep(1)
        logger.info("Vision queue worker stopped")

    async def stop(self) -> None:
        self._stop_event.set()
