from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.models import ChatSession
from app.schemas.chat import ChatAnswer
from app.services.memory.service import MemoryService
from app.services.rag.service import RagService


class ChatGraphState(TypedDict, total=False):
    session_id: str
    user_message: str
    short_term_summary: str
    used_memory: list[str]
    rag_answer: ChatAnswer


def run_chat_graph(db: Session, session: ChatSession, question: str) -> ChatGraphState:
    memory_service = MemoryService(db)
    rag_service = RagService(db)

    def load_session_context(_: ChatGraphState) -> ChatGraphState:
        return {"session_id": session.id, "user_message": question}

    def recall_memory(_: ChatGraphState) -> ChatGraphState:
        summary = memory_service.get_latest_summary(session.id)
        memories = memory_service.recall_long_term_memory(session.project_id, question)
        return {
            "short_term_summary": summary,
            "used_memory": [item.content for item in memories],
        }

    def run_rag(state: ChatGraphState) -> ChatGraphState:
        answer = rag_service.answer(
            project_id=session.project_id,
            question=question,
            short_term_summary=state.get("short_term_summary", ""),
            long_term_memory=state.get("used_memory", []),
        )
        return {"rag_answer": answer}

    def persist_messages(state: ChatGraphState) -> ChatGraphState:
        memory_service.append_message(session.id, "user", question)
        memory_service.append_message(
            session.id,
            "assistant",
            state["rag_answer"].answer,
            citations=state["rag_answer"].citations,
        )
        return state

    graph = StateGraph(ChatGraphState)
    graph.add_node("load_session_context", load_session_context)
    graph.add_node("recall_memory", recall_memory)
    graph.add_node("run_rag", run_rag)
    graph.add_node("persist_messages", persist_messages)
    graph.set_entry_point("load_session_context")
    graph.add_edge("load_session_context", "recall_memory")
    graph.add_edge("recall_memory", "run_rag")
    graph.add_edge("run_rag", "persist_messages")
    graph.add_edge("persist_messages", END)
    return graph.compile().invoke({})
