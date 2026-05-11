from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

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

    Base.metadata.create_all(bind=engine)
    _ensure_schema_compatibility()
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


def _ensure_schema_compatibility() -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "knowledge_documents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("knowledge_documents")}
    statements = []
    if "error_message" not in columns:
        statements.append("ALTER TABLE knowledge_documents ADD COLUMN error_message TEXT")
    if "metadata_json" not in columns:
        statements.append("ALTER TABLE knowledge_documents ADD COLUMN metadata_json JSON DEFAULT '{}'")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
