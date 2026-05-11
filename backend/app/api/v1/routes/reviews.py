from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import CodeReviewResult, CodeReviewTask
from app.schemas.common import ApiResponse
from app.schemas.review import ReviewRequest, ReviewResultRead, ReviewTaskRead
from app.services.commit_context.service import CommitContextError
from app.services.review.service import ReviewService
from app.services.tasks.dispatcher import enqueue_review_task

router = APIRouter()


@router.post("/projects/{project_id}/reviews", response_model=ApiResponse[ReviewTaskRead])
def create_review(
    project_id: str, payload: ReviewRequest, db: Session = Depends(get_db)
) -> ApiResponse[ReviewTaskRead]:
    service = ReviewService(db)
    task = service.create_task(project_id=project_id, user_id="demo-user", payload=payload)
    task.status = "queued"
    task.progress_stage = "queued"
    db.add(task)
    db.commit()
    try:
        enqueue_review_task(task.id)
    except CommitContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=ReviewTaskRead.model_validate(task))


@router.post("/projects/{project_id}/reviews/from-github", response_model=ApiResponse[ReviewTaskRead])
def create_review_from_github(
    project_id: str, payload: ReviewRequest, db: Session = Depends(get_db)
) -> ApiResponse[ReviewTaskRead]:
    if payload.source_type not in {"github_pr", "github_commit"}:
        raise HTTPException(status_code=400, detail="source_type must be github_pr or github_commit")
    service = ReviewService(db)
    task = service.create_task(project_id=project_id, user_id="demo-user", payload=payload)
    task.status = "queued"
    task.progress_stage = "queued"
    db.add(task)
    db.commit()
    try:
        enqueue_review_task(task.id)
    except CommitContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=ReviewTaskRead.model_validate(task))


@router.get("/projects/{project_id}/reviews", response_model=ApiResponse[list[ReviewTaskRead]])
def list_review_tasks(
    project_id: str, db: Session = Depends(get_db)
) -> ApiResponse[list[ReviewTaskRead]]:
    tasks = ReviewService(db).list_tasks(project_id)
    return ApiResponse(data=[ReviewTaskRead.model_validate(task) for task in tasks])


@router.get("/reviews/{task_id}", response_model=ApiResponse[ReviewTaskRead])
def get_review_task(task_id: str, db: Session = Depends(get_db)) -> ApiResponse[ReviewTaskRead]:
    task = db.get(CodeReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="review task not found")
    return ApiResponse(data=ReviewTaskRead.model_validate(task))


@router.get("/reviews/{task_id}/result", response_model=ApiResponse[ReviewResultRead])
def get_review_result(task_id: str, db: Session = Depends(get_db)) -> ApiResponse[ReviewResultRead]:
    result = db.query(CodeReviewResult).filter(CodeReviewResult.task_id == task_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="review result not found")
    return ApiResponse(
        data=ReviewResultRead(
            summary=result.summary,
            overall_risk=result.raw_output_json.get("overall_risk", "medium"),
            findings=result.findings_json,
            suggestions=result.suggestions_json,
            positive_notes=result.raw_output_json.get("positive_notes", []),
            uncertain_points=result.raw_output_json.get("uncertain_points", []),
        )
    )
