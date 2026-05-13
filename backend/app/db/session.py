from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import entities  # noqa: F401
    from app.models import Project, User

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "demo@example.com").first()
        if user is None:
            user = User(email="demo@example.com", name="Demo User", role="owner")
            db.add(user)
            db.flush()
        project = db.query(Project).filter(Project.slug == "demo-platform").first()
        if project is None:
            project = Project(
                owner_id=user.id,
                name="实验室 AI 研发平台",
                slug="demo-platform",
                description="默认演示项目",
                primary_language="python",
            )
            db.add(project)
        db.commit()
