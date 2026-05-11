from app.db.session import SessionLocal
from app.models import TestGenerationTask
from app.services.testgen.service import TestGenerationService
from worker.app.celery_app import celery_app


@celery_app.task(name="worker.app.jobs.testgen.run_testgen_job")
def run_testgen_job(task_id: str) -> dict:
    with SessionLocal() as db:
        task = db.get(TestGenerationTask, task_id)
        if task is None:
            return {"task_id": task_id, "status": "missing"}
        service = TestGenerationService(db)
        service.run_task(task)
        return {"task_id": task_id, "status": task.status}
