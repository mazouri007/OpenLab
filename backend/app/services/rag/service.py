from __future__ import annotations

import math
from hashlib import sha256
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from app.agents.output_models import RagAnswerOutput
from app.agents.prompt_catalog import RAG_ANSWER_PROMPT, RAG_REWRITE_PROMPT
from app.models import KnowledgeChunk, KnowledgeDocument
from app.schemas.chat import ChatAnswer
from app.schemas.kb import KnowledgeDocumentCreate
from app.services.llm.exceptions import LLMConfigurationError, LLMInvocationError
from app.services.llm.litellm_provider import LiteLLMProvider
from app.services.llm.provider_resolver import resolve_model_config


class RagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm_provider = LiteLLMProvider()

    def create_document(self, project_id: str, payload: KnowledgeDocumentCreate) -> KnowledgeDocument:
        document = KnowledgeDocument(
            project_id=project_id,
            title=payload.title,
            source_type=payload.source_type,
            source_name=payload.source_name,
            raw_content=payload.raw_text,
            content_hash=sha256(payload.raw_text.encode("utf-8")).hexdigest(),
            parse_status="pending",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def index_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        document.parse_status = "indexing"
        self.db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
        model_config = None
        try:
            model_config = resolve_model_config(self.db, document.project_id)
        except LLMConfigurationError:
            model_config = None

        chunks = self._semantic_chunks(document.raw_content or "", document.title, document.source_name)
        embeddings: list[list[float]] | None = None
        if chunks and model_config is not None:
            try:
                embeddings = self.llm_provider.embed_texts(
                    [item["content"] for item in chunks], model_config=model_config
                )
            except LLMInvocationError:
                embeddings = None

        for index, chunk in enumerate(chunks):
            metadata = {
                "title": document.title,
                "source_type": document.source_type,
                "source_name": document.source_name,
                "section": chunk["section"],
            }
            if embeddings:
                metadata["embedding"] = embeddings[index]
            self.db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    project_id=document.project_id,
                    chunk_index=index,
                    content=chunk["content"],
                    token_count=len(chunk["content"].split()),
                    metadata_json=metadata,
                )
            )
        document.parse_status = "indexed"
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def answer(
        self,
        project_id: str,
        question: str,
        short_term_summary: str = "",
        long_term_memory: list[str] | None = None,
    ) -> ChatAnswer:
        model_config = resolve_model_config(self.db, project_id)
        rewritten_queries = self._rewrite_query(question, model_config)
        chunks = self._hybrid_retrieve(project_id, rewritten_queries, model_config)
        context = self._build_context(chunks)
        answer_result = self._answer_with_citations(
            question=question,
            context=context,
            rewritten_queries=rewritten_queries,
            short_term_summary=short_term_summary,
            long_term_memory=long_term_memory or [],
            model_config=model_config,
        )
        return ChatAnswer(
            answer=answer_result.answer,
            citations=[item.model_dump() for item in answer_result.citations],
            used_memory=long_term_memory or [],
            used_documents=[item.source_title or item.chunk_id for item in answer_result.citations],
            rewritten_queries=rewritten_queries,
            reasoning_summary=answer_result.reasoning_summary,
            confidence=answer_result.confidence,
        )

    def _rewrite_query(self, question: str, model_config: dict[str, Any]) -> list[str]:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_REWRITE_PROMPT),
                ("user", "用户问题：{question}"),
            ]
        )
        messages = prompt.invoke({"question": question}).to_messages()
        try:
            rewritten = self.llm_provider.chat_json(
                system_prompt=messages[0].content,
                user_prompt=messages[1].content,
                schema_name="QueryRewriteOutput",
                model_config=model_config,
            )
            return rewritten.get(
                "rewritten_queries",
                [question, f"实验室规范 {question}", f"历史案例 {question}"],
            )
        except Exception:  # noqa: BLE001
            return [question, f"实验室规范 {question}", f"项目背景 {question}"]

    def _hybrid_retrieve(
        self, project_id: str, queries: list[str], model_config: dict[str, Any]
    ) -> list[KnowledgeChunk]:
        chunks = self.db.query(KnowledgeChunk).filter(KnowledgeChunk.project_id == project_id).all()
        if not chunks:
            return []
        keyword_scores: dict[str, float] = {}
        for chunk in chunks:
            text = chunk.content.lower()
            score = 0.0
            for query in queries:
                for token in query.lower().split():
                    if token and token in text:
                        score += 1.0
            keyword_scores[chunk.id] = score

        vector_scores: dict[str, float] = {}
        try:
            query_vectors = self.llm_provider.embed_texts(queries, model_config=model_config)
            aggregate_query = self._average_vector(query_vectors)
            for chunk in chunks:
                embedding = chunk.metadata_json.get("embedding")
                if embedding:
                    vector_scores[chunk.id] = self._cosine_similarity(aggregate_query, embedding)
        except Exception:  # noqa: BLE001
            vector_scores = {}

        ranked = sorted(
            chunks,
            key=lambda chunk: keyword_scores.get(chunk.id, 0.0) + vector_scores.get(chunk.id, 0.0),
            reverse=True,
        )
        deduped: list[KnowledgeChunk] = []
        seen = set()
        for chunk in ranked:
            if chunk.content in seen:
                continue
            seen.add(chunk.content)
            deduped.append(chunk)
        return deduped[:6]

    def _build_context(self, chunks: list[KnowledgeChunk]) -> str:
        blocks = []
        for chunk in chunks:
            blocks.append(
                f"[{chunk.id}] 标题：{chunk.metadata_json.get('title')}\n"
                f"来源：{chunk.metadata_json.get('source_name')}\n"
                f"内容：{chunk.content}"
            )
        return "\n\n".join(blocks)

    def _answer_with_citations(
        self,
        question: str,
        context: str,
        rewritten_queries: list[str],
        short_term_summary: str,
        long_term_memory: list[str],
        model_config: dict[str, Any],
    ) -> RagAnswerOutput:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_ANSWER_PROMPT),
                (
                    "user",
                    "问题：{question}\n重写查询：{rewritten_queries}\n短期摘要：{short_term_summary}\n"
                    "长期记忆：{long_term_memory}\n知识上下文：\n{context}",
                ),
            ]
        )
        messages = prompt.invoke(
            {
                "question": question,
                "rewritten_queries": rewritten_queries,
                "short_term_summary": short_term_summary,
                "long_term_memory": long_term_memory,
                "context": context or "无命中上下文",
            }
        ).to_messages()
        result = self.llm_provider.chat_json(
            system_prompt=messages[0].content,
            user_prompt=messages[1].content,
            schema_name="RagAnswerOutput",
            model_config=model_config,
        )
        if not result.get("citations"):
            result["citations"] = [
                {
                    "chunk_id": "no-context",
                    "snippet": context[:160],
                    "source_type": "knowledge_chunk",
                    "source_title": "No Context",
                }
            ]
        return RagAnswerOutput.model_validate(result)

    @staticmethod
    def _semantic_chunks(raw_text: str, title: str, source_name: str | None) -> list[dict[str, str]]:
        blocks = [block.strip() for block in raw_text.split("\n\n") if block.strip()]
        if not blocks:
            blocks = [raw_text.strip()] if raw_text.strip() else []
        chunks: list[dict[str, str]] = []
        buffer = ""
        section_index = 1
        for block in blocks:
            if len(buffer) + len(block) < 650:
                buffer = f"{buffer}\n\n{block}".strip()
                continue
            if buffer:
                chunks.append(
                    {
                        "content": buffer,
                        "section": f"{title}:{source_name or 'section'}:{section_index}",
                    }
                )
                section_index += 1
            buffer = block
        if buffer:
            chunks.append(
                {
                    "content": buffer,
                    "section": f"{title}:{source_name or 'section'}:{section_index}",
                }
            )
        return chunks

    @staticmethod
    def _average_vector(vectors: list[list[float]]) -> list[float]:
        if not vectors:
            return []
        size = len(vectors[0])
        return [sum(vector[idx] for vector in vectors) / len(vectors) for idx in range(size)]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)
