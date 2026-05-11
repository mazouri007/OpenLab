from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "lab_ai_reviewer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_always_eager = settings.celery_task_always_eager
celery_app.conf.task_routes = {
    "worker.app.jobs.review.run_review_job": {"queue": "review"},
    "worker.app.jobs.testgen.run_testgen_job": {"queue": "testgen"},
    "worker.app.jobs.index.run_index_job": {"queue": "index"},
}
