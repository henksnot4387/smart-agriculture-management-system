from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status

from app.ai.vision.dependencies import get_vision_task_service
from app.ai.vision.service import VisionTaskService
from app.core.security import require_api_token
from app.schemas.vision import VisionRuntimeResponse, VisionTaskListResponse, VisionTaskResponse

router = APIRouter(
    prefix="/api/vision",
    tags=["vision"],
    dependencies=[Depends(require_api_token)],
)


@router.post("/tasks", response_model=VisionTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_vision_task(
    file: UploadFile = File(...),
    source: str = Query(default="MOBILE"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    service: VisionTaskService = Depends(get_vision_task_service),
) -> VisionTaskResponse:
    file_bytes = await file.read()
    try:
        return await service.submit_task(
            file_name=file.filename,
            content_type=file.content_type,
            file_bytes=file_bytes,
            source=source.strip().upper(),
            uploaded_by_id=x_user_id.strip() if x_user_id else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/tasks/{task_id}", response_model=VisionTaskResponse)
async def get_vision_task(
    task_id: str,
    service: VisionTaskService = Depends(get_vision_task_service),
) -> VisionTaskResponse:
    task = await service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision task not found.")
    return task


@router.get("/tasks", response_model=VisionTaskListResponse)
async def list_vision_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    service: VisionTaskService = Depends(get_vision_task_service),
) -> VisionTaskListResponse:
    return await service.list_tasks(limit=limit)


@router.get("/runtime", response_model=VisionRuntimeResponse)
async def get_vision_runtime(
    service: VisionTaskService = Depends(get_vision_task_service),
) -> VisionRuntimeResponse:
    return await service.get_runtime()
