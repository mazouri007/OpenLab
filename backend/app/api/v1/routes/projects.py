from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, User
from app.schemas.common import ApiResponse
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter()


@router.post("", response_model=ApiResponse[ProjectRead])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ApiResponse[ProjectRead]:
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if user is None:
        user = User(email="demo@example.com", name="Demo User", role="owner")
        db.add(user)
        db.commit()
        db.refresh(user)
    project = Project(
        owner_id=user.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        primary_language=payload.primary_language,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ApiResponse(data=ProjectRead.model_validate(project))


@router.get("", response_model=ApiResponse[list[ProjectRead]])
def list_projects(db: Session = Depends(get_db)) -> ApiResponse[list[ProjectRead]]:
    items = db.query(Project).order_by(Project.created_at.desc()).all()
    return ApiResponse(data=[ProjectRead.model_validate(item) for item in items])

