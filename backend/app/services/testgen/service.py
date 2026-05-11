from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.testgen_graph import run_testgen_graph
from app.models import TestGenerationResult, TestGenerationTask
from app.schemas.testgen import TestGenerationRequest
from app.services.llm.provider_resolver import resolve_model_config


class TestGenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(
        self, project_id: str, user_id: str, payload: TestGenerationRequest
    ) -> TestGenerationTask:
        task = TestGenerationTask(
            project_id=project_id,
            user_id=user_id,
            language=payload.language,
            framework=payload.framework,
            target_name=payload.target_name,
            input_code=payload.code,
            extra_requirements=payload.extra_requirements,
            status="pending",
            progress_stage="created",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_tasks(self, project_id: str) -> list[TestGenerationTask]:
        return (
            self.db.query(TestGenerationTask)
            .filter(TestGenerationTask.project_id == project_id)
            .order_by(TestGenerationTask.updated_at.desc())
            .all()
        )

    def run_task(self, task: TestGenerationTask) -> TestGenerationResult:
        model_config = resolve_model_config(self.db, task.project_id)
        try:
            graph_result = run_testgen_graph(self.db, task, model_config)
            code_result = graph_result["code_result"]
            result = self.db.query(TestGenerationResult).filter(TestGenerationResult.task_id == task.id).first()
            if result is None:
                result = TestGenerationResult(task_id=task.id, test_code="")
            result.test_code = code_result["test_code"]
            result.scenarios_json = graph_result["plan_result"]["scenarios"]
            result.self_check_report_json = code_result["self_check_report"]
            result.raw_output_json = {
                "plan_result": graph_result["plan_result"],
                "code_result": code_result,
                "model_name": model_config["chat_model"],
            }
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
