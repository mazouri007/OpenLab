from app.db.session import SessionLocal
from app.models import CodeReviewTask
from app.services.review.service import ReviewService
from worker.app.celery_app import celery_app


@celery_app.task(name="worker.app.jobs.review.run_review_job")
def run_review_job(task_id: str) -> dict:
    with SessionLocal() as db:
        task = db.get(CodeReviewTask, task_id)
        if task is None:
            return {"task_id": task_id, "status": "missing"}
        service = ReviewService(db)
        service.run_task(task)
        return {"task_id": task_id, "status": task.status}
