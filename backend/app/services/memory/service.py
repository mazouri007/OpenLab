from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from app.agents.prompt_catalog import MEMORY_EXTRACTION_PROMPT
from app.models import ChatMessage, ChatSession, LongTermMemory, MemorySummary
from app.services.llm.langchain_provider import LangChainLLMProvider
from app.services.llm.provider_resolver import resolve_model_config


class MemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm_provider = LangChainLLMProvider()

    def create_session(self, project_id: str, user_id: str, title: str) -> ChatSession:
        session = ChatSession(project_id=project_id, user_id=user_id, title=title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, project_id: str) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.project_id == project_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def append_message(
        self, session_id: str, role: str, content: str, citations: list[dict] | None = None
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations_json=citations or [],
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_recent_messages(self, session_id: str, window_size: int = 8) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(window_size)
            .all()[::-1]
        )

    def get_latest_summary(self, session_id: str) -> str:
        summary = (
            self.db.query(MemorySummary)
            .filter(MemorySummary.session_id == session_id)
            .order_by(MemorySummary.created_at.desc())
            .first()
        )
        return summary.summary_text if summary else ""

    def summarize_if_needed(self, session_id: str, window_size: int = 12) -> MemorySummary | None:
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        if len(messages) <= window_size:
            return None
        older_messages = messages[:-window_size]
        summary_text = "\n".join(f"{item.role}: {item.content[:120]}" for item in older_messages)
        summary = MemorySummary(
            session_id=session_id,
            summary_text=summary_text,
            covered_until_message_id=older_messages[-1].id,
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary

    def recall_long_term_memory(self, project_id: str, query: str, limit: int = 3) -> list[LongTermMemory]:
        candidates = (
            self.db.query(LongTermMemory)
            .filter(LongTermMemory.project_id == project_id)
            .order_by(LongTermMemory.importance.desc(), LongTermMemory.updated_at.desc())
            .all()
        )
        scored = []
        lower_query = query.lower()
        for memory in candidates:
            score = memory.importance
            if lower_query in memory.content.lower():
                score += 1.0
            scored.append((score, memory))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def maybe_extract_long_term_memory(self, session: ChatSession, user_message: str, answer: str) -> None:
        model_config = resolve_model_config(self.db, session.project_id)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", MEMORY_EXTRACTION_PROMPT),
                (
                    "user",
                    "用户问题：{user_message}\n助手回答：{answer}\n"
                    '只输出 JSON，格式为 {{"should_store":bool,"memory_type":"","content":"","tags":[]}}',
                ),
            ]
        )
        messages = prompt.invoke({"user_message": user_message, "answer": answer}).to_messages()
        result = self.llm_provider.chat_json(
            system_prompt=messages[0].content,
            user_prompt=messages[1].content,
            schema_name="MemoryExtractionOutput",
            model_config=model_config,
        )
        if result.get("should_store") and result.get("content"):
            memory = LongTermMemory(
                project_id=session.project_id,
                user_id=session.user_id,
                memory_type=result.get("memory_type", "preference"),
                content=result["content"],
                tags_json=result.get("tags", []),
                importance=0.8,
                source_session_id=session.id,
            )
            self.db.add(memory)
            self.db.commit()
