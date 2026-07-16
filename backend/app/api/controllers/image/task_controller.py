"""HTTP routes for selecting image-annotation tasks."""

from fastapi import APIRouter, Depends

from backend.app.api.dependencies.image import get_task_service
from backend.app.api.schemas.image import TaskInfo
from backend.app.services.tasks import TaskService


router = APIRouter(prefix="/api/v1", tags=["tasks"])


@router.get("/tasks", response_model=list[TaskInfo])
def get_tasks(service: TaskService = Depends(get_task_service)) -> list[TaskInfo]:
    return [TaskInfo.from_domain(task) for task in service.list_tasks()]
