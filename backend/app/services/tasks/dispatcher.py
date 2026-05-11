from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import CodeReviewTask, KnowledgeDocument, TestGenerationTask
from app.services.rag.service import RagService
from app.services.review.service import ReviewService
from app.services.testgen.service import TestGenerationService


def enqueue_review_task(task_id: str) -> None:
    if not get_settings().celery_task_always_eager:
        from worker.app.jobs.review import run_review_job

        run_review_job.delay(task_id)
        return
    with SessionLocal() as db:
        task = db.get(CodeReviewTask, task_id)
        if task is not None:
            ReviewService(db).run_task(task)


def enqueue_testgen_task(task_id: str) -> None:
    if not get_settings().celery_task_always_eager:
        from worker.app.jobs.testgen import run_testgen_job

        run_testgen_job.delay(task_id)
        return
    with SessionLocal() as db:
        task = db.get(TestGenerationTask, task_id)
        if task is not None:
            TestGenerationService(db).run_task(task)


def enqueue_index_task(document_id: str) -> None:
    if not get_settings().celery_task_always_eager:
        from worker.app.jobs.index import run_index_job

        run_index_job.delay(document_id)
        return
    with SessionLocal() as db:
        document = db.get(KnowledgeDocument, document_id)
        if document is not None:
            RagService(db).index_document(document)
