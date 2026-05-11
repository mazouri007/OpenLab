from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.review_graph import run_review_graph
from app.models import CodeReviewResult, CodeReviewTask
from app.schemas.review import ReviewRequest
from app.services.llm.provider_resolver import resolve_model_config


class ReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(self, project_id: str, user_id: str, payload: ReviewRequest) -> CodeReviewTask:
        task = CodeReviewTask(
            project_id=project_id,
            user_id=user_id,
            source_type=payload.source_type,
            language=payload.language,
            title=payload.title,
            input_payload_json=payload.model_dump(),
            status="pending",
            progress_stage="created",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_tasks(self, project_id: str) -> list[CodeReviewTask]:
        return (
            self.db.query(CodeReviewTask)
            .filter(CodeReviewTask.project_id == project_id)
            .order_by(CodeReviewTask.updated_at.desc())
            .all()
        )

    def run_task(self, task: CodeReviewTask) -> CodeReviewResult:
        model_config = resolve_model_config(self.db, task.project_id)
        try:
            graph_result = run_review_graph(self.db, task, model_config)
            result_payload = graph_result["result"]
            result = self.db.query(CodeReviewResult).filter(CodeReviewResult.task_id == task.id).first()
            if result is None:
                result = CodeReviewResult(task_id=task.id, summary="", overall_score=0.0)
            result.summary = result_payload["summary"]
            result.overall_score = result_payload["overall_score"]
            result.findings_json = result_payload["findings"]
            result.suggestions_json = result_payload["suggestions"]
            result.raw_output_json = result_payload
            task.status = "completed"
            task.progress_stage = "completed"
            task.error_message = None
            self.db.add(result)
            self.db.add(task)
            self.db.commit()
            self.db.refresh(result)
            return result
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            task.progress_stage = "failed"
            task.error_message = str(exc)
            self.db.add(task)
            self.db.commit()
            raise
