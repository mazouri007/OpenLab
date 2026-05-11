from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.task import TaskStatusRead
from app.services.tasks.service import TaskQueryService

router = APIRouter()


@router.get("/tasks/{task_id}", response_model=ApiResponse[TaskStatusRead])
def get_task_status(task_id: str, db: Session = Depends(get_db)) -> ApiResponse[TaskStatusRead]:
    status = TaskQueryService(db).get_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="task not found")
    return ApiResponse(data=TaskStatusRead(**status))

