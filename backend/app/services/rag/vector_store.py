from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings


@dataclass
class VectorSearchHit:
    chunk_id: str
    score: float


class RagVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.top_k = settings.rag_vector_top_k

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        self.collection.upsert(
            ids=[item["id"] for item in chunks],
            embeddings=[item["embedding"] for item in chunks],
            documents=[item["document"] for item in chunks],
            metadatas=[_metadata(item["metadata"]) for item in chunks],
        )

    def query(self, project_id: str, embedding: list[float], top_k: int | None = None) -> list[VectorSearchHit]:
        if not embedding:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k or self.top_k,
            where={"project_id": project_id},
            include=["distances"],
        )
        ids = result.get("ids", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []
        hits: list[VectorSearchHit] = []
        for index, chunk_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 1.0
            hits.append(VectorSearchHit(chunk_id=str(chunk_id), score=max(0.0, 1.0 - distance)))
        return hits


def _metadata(raw: dict[str, Any]) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = str(value)
    return metadata
