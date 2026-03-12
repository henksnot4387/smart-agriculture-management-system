from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.admin_observability import router as admin_observability_router
from app.api.admin_scheduler import router as admin_scheduler_router
from app.api.copilot import legacy_router as copilot_legacy_router
from app.api.copilot import router as ai_insights_router
from app.api.health import router as health_router
from app.api.hoogendoorn import router as hoogendoorn_router
from app.api.ops import router as ops_router
from app.api.sensor import router as sensor_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.api.vision import router as vision_router
from app.api.ws import router as ws_router
from app.ai.vision.dependencies import start_vision_worker, stop_vision_worker
from app.core.config import REPO_ROOT, settings
from app.core.logging import setup_logging
from app.middleware.exception_handler import ExceptionHandlingMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.observability import get_observability_service
from app.scheduler.service import get_scheduler_service

setup_logging(settings.log_level)
logger = logging.getLogger("app.main")
local_storage_root = Path(settings.local_storage_root)
if not local_storage_root.is_absolute():
    local_storage_root = (REPO_ROOT / local_storage_root).resolve()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting backend application", extra={"environment": settings.app_env})
    get_scheduler_service().bootstrap()
    get_observability_service().bootstrap()
    await start_vision_worker()
    yield
    await stop_vision_worker()
    logger.info("Stopping backend application")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(ExceptionHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(health_router)
app.include_router(hoogendoorn_router, prefix="/integrations/hoogendoorn")
app.include_router(ops_router)
app.include_router(sensor_router)
app.include_router(settings_router)
app.include_router(tasks_router)
app.include_router(vision_router)
app.include_router(ai_insights_router)
app.include_router(copilot_legacy_router)
app.include_router(ws_router)
app.include_router(admin_scheduler_router)
app.include_router(admin_observability_router)
app.mount("/files", StaticFiles(directory=str(local_storage_root), check_dir=False), name="files")
