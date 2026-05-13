from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.session import SessionLocal  # noqa: E402
from app.models import KnowledgeDocument  # noqa: E402
from app.services.rag.service import RagService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild ChromaDB vectors from SQL knowledge docs.")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--document-id", default=None)
    args = parser.parse_args()

    with SessionLocal() as db:
        query = db.query(KnowledgeDocument)
        if args.project_id:
            query = query.filter(KnowledgeDocument.project_id == args.project_id)
        if args.document_id:
            query = query.filter(KnowledgeDocument.id == args.document_id)
        documents = query.all()
        service = RagService(db)
        for document in documents:
            service.index_document(document)
            print(f"Rebuilt {document.id} ({document.title})")
    print(f"Rebuilt ChromaDB vectors for {len(documents)} document(s).")


if __name__ == "__main__":
    main()
