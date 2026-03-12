from __future__ import annotations

import asyncio
from functools import lru_cache

from redis import Redis

from app.ai.vision.events import VisionTaskEventHub
from app.ai.vision.inference import build_inference_engine
from app.ai.vision.service import VisionTaskService
from app.ai.vision.storage import build_storage_service
from app.core.config import settings
from app.repositories.vision import VisionTaskRepository
from app.workers.vision_worker import VisionQueueWorker

_worker: VisionQueueWorker | None = None
_worker_task: asyncio.Task[None] | None = None


@lru_cache
def get_vision_event_hub() -> VisionTaskEventHub:
    return VisionTaskEventHub()


@lru_cache
def get_vision_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=False)


@lru_cache
def get_vision_task_service() -> VisionTaskService:
    return VisionTaskService(
        settings=settings,
        repository=VisionTaskRepository(settings),
        storage=build_storage_service(settings),
        inference=build_inference_engine(settings),
        redis_client=get_vision_redis_client(),
        event_hub=get_vision_event_hub(),
    )


def get_vision_local_storage_root() -> str | None:
    root = get_vision_task_service().storage_root_path
    return str(root) if root else None


async def start_vision_worker() -> None:
    global _worker, _worker_task
    if _worker_task and not _worker_task.done():
        return

    _worker = VisionQueueWorker(service=get_vision_task_service())
    _worker_task = asyncio.create_task(_worker.run_forever(), name="vision-queue-worker")


async def stop_vision_worker() -> None:
    global _worker, _worker_task

    if _worker:
        await _worker.stop()

    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass

    _worker = None
    _worker_task = None

    event_hub = get_vision_event_hub()
    await event_hub.close_all()

    redis_client = get_vision_redis_client()
    redis_client.close()
    get_vision_task_service.cache_clear()
    get_vision_redis_client.cache_clear()
    get_vision_event_hub.cache_clear()
