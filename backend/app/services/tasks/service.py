from sqlalchemy.orm import Session

from app.models import CodeReviewTask, TestGenerationTask


class TaskQueryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_status(self, task_id: str) -> dict | None:
        review_task = self.db.get(CodeReviewTask, task_id)
        if review_task:
            return {
                "id": review_task.id,
                "task_type": "review",
                "status": review_task.status,
                "progress_stage": review_task.progress_stage,
                "error_message": review_task.error_message,
                "updated_at": review_task.updated_at.isoformat() if review_task.updated_at else None,
            }
        test_task = self.db.get(TestGenerationTask, task_id)
        if test_task:
            return {
                "id": test_task.id,
                "task_type": "testgen",
                "status": test_task.status,
                "progress_stage": test_task.progress_stage,
                "error_message": test_task.error_message,
                "updated_at": test_task.updated_at.isoformat() if test_task.updated_at else None,
            }
        return None
