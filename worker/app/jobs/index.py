from app.db.session import SessionLocal
from app.models import KnowledgeDocument
from app.services.rag.service import RagService
from worker.app.celery_app import celery_app


@celery_app.task(name="worker.app.jobs.index.run_index_job")
def run_index_job(document_id: str) -> dict:
    with SessionLocal() as db:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            return {"document_id": document_id, "status": "missing"}
        service = RagService(db)
        service.index_document(document)
        return {"document_id": document_id, "status": document.parse_status}
