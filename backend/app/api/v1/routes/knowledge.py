from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import KnowledgeChunk, KnowledgeDocument
from app.schemas.common import ApiResponse
from app.schemas.kb import KnowledgeDocumentCreate, KnowledgeDocumentRead
from app.services.rag.service import RagService
from app.services.rag.document_parser import UnsupportedDocumentTypeError
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
    return ApiResponse(data=_document_read(db, document))


@router.post("/documents/upload", response_model=ApiResponse[KnowledgeDocumentRead])
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[KnowledgeDocumentRead]:
    service = RagService(db)
    content = await file.read()
    filename = file.filename or "uploaded-document"
    try:
        document = service.create_file_document(
            project_id=project_id,
            filename=filename,
            content=content,
            title=title,
            content_type=file.content_type,
        )
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    if document.parse_status != "failed":
        document.parse_status = "queued"
        db.add(document)
        db.commit()
        enqueue_index_task(document.id)
    return ApiResponse(data=_document_read(db, document))


@router.get("/documents", response_model=ApiResponse[list[KnowledgeDocumentRead]])
def list_documents(project_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[KnowledgeDocumentRead]]:
    items = db.query(KnowledgeDocument).filter(KnowledgeDocument.project_id == project_id).all()
    return ApiResponse(data=[_document_read(db, item) for item in items])


def _document_read(db: Session, document: KnowledgeDocument) -> KnowledgeDocumentRead:
    item = KnowledgeDocumentRead.model_validate(document)
    item.chunk_count = (
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).count()
    )
    return item
