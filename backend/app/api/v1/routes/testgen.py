from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import TestGenerationResult, TestGenerationTask
from app.schemas.common import ApiResponse
from app.schemas.testgen import (
    TestGenerationRequest,
    TestGenerationResultRead,
    TestGenerationTaskRead,
)
from app.services.testgen.service import TestGenerationService
from app.services.tasks.dispatcher import enqueue_testgen_task

router = APIRouter()


@router.post("/projects/{project_id}/test-generations", response_model=ApiResponse[TestGenerationTaskRead])
def create_test_generation(
    project_id: str, payload: TestGenerationRequest, db: Session = Depends(get_db)
) -> ApiResponse[TestGenerationTaskRead]:
    service = TestGenerationService(db)
    task = service.create_task(project_id=project_id, user_id="demo-user", payload=payload)
    task.status = "queued"
    task.progress_stage = "queued"
    db.add(task)
    db.commit()
    enqueue_testgen_task(task.id)
    return ApiResponse(data=TestGenerationTaskRead.model_validate(task))


@router.post(
    "/projects/{project_id}/test-generations/from-github",
    response_model=ApiResponse[TestGenerationTaskRead],
)
def create_test_generation_from_github(
    project_id: str, payload: TestGenerationRequest, db: Session = Depends(get_db)
) -> ApiResponse[TestGenerationTaskRead]:
    service = TestGenerationService(db)
    task = service.create_task(project_id=project_id, user_id="demo-user", payload=payload)
    task.status = "queued"
    task.progress_stage = "queued"
    db.add(task)
    db.commit()
    enqueue_testgen_task(task.id)
    return ApiResponse(data=TestGenerationTaskRead.model_validate(task))


@router.get("/projects/{project_id}/test-generations", response_model=ApiResponse[list[TestGenerationTaskRead]])
def list_test_generation_tasks(
    project_id: str, db: Session = Depends(get_db)
) -> ApiResponse[list[TestGenerationTaskRead]]:
    tasks = TestGenerationService(db).list_tasks(project_id)
    return ApiResponse(data=[TestGenerationTaskRead.model_validate(task) for task in tasks])


@router.get("/test-generations/{task_id}", response_model=ApiResponse[TestGenerationTaskRead])
def get_test_generation_task(
    task_id: str, db: Session = Depends(get_db)
) -> ApiResponse[TestGenerationTaskRead]:
    task = db.get(TestGenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="test generation task not found")
    return ApiResponse(data=TestGenerationTaskRead.model_validate(task))


@router.get("/test-generations/{task_id}/result", response_model=ApiResponse[TestGenerationResultRead])
def get_test_generation_result(
    task_id: str, db: Session = Depends(get_db)
) -> ApiResponse[TestGenerationResultRead]:
    result = db.query(TestGenerationResult).filter(TestGenerationResult.task_id == task_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="test generation result not found")
    return ApiResponse(
        data=TestGenerationResultRead(
            test_code=result.test_code,
            scenarios=result.scenarios_json,
            self_check_report=result.self_check_report_json,
        )
    )
