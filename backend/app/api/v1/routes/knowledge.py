from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import KnowledgeDocument
from app.schemas.common import ApiResponse
from app.schemas.kb import KnowledgeDocumentCreate, KnowledgeDocumentRead
from app.services.rag.service import RagService
from app.services.tasks.dispatcher import enqueue_index_task

router = APIRouter(prefix="/projects/{project_id}/kb")


@router.post("/documents", response_model=ApiResponse[KnowledgeDocumentRead])
def create_document(
    project_id: str, payload: KnowledgeDocumentCreate, db: Session = Depends(get_db)
) -> ApiResponse[KnowledgeDocumentRead]:
    service = RagService(db)
    document = service.create_document(project_id, payload)
    document.parse_status = "queued"
    db.add(document)
    db.commit()
    enqueue_index_task(document.id)
    return ApiResponse(data=KnowledgeDocumentRead.model_validate(document))


@router.get("/documents", response_model=ApiResponse[list[KnowledgeDocumentRead]])
def list_documents(project_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[KnowledgeDocumentRead]]:
    items = db.query(KnowledgeDocument).filter(KnowledgeDocument.project_id == project_id).all()
    return ApiResponse(data=[KnowledgeDocumentRead.model_validate(item) for item in items])
