from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import PromptTemplate
from app.schemas.common import ApiResponse
from app.schemas.prompt import PromptTemplateCreate, PromptTemplateRead

router = APIRouter(prefix="/projects/{project_id}/prompts")


@router.post("", response_model=ApiResponse[PromptTemplateRead])
def create_prompt_template(
    project_id: str, payload: PromptTemplateCreate, db: Session = Depends(get_db)
) -> ApiResponse[PromptTemplateRead]:
    item = PromptTemplate(project_id=project_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return ApiResponse(data=PromptTemplateRead.model_validate(item))


@router.get("", response_model=ApiResponse[list[PromptTemplateRead]])
def list_prompt_templates(project_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[PromptTemplateRead]]:
    items = db.query(PromptTemplate).filter(PromptTemplate.project_id == project_id).all()
    return ApiResponse(data=[PromptTemplateRead.model_validate(item) for item in items])

