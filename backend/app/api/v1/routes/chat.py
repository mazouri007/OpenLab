from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.chat_graph import run_chat_graph
from app.db.session import get_db
from app.models import ChatMessage, ChatSession
from app.schemas.chat import ChatAnswer, ChatMessageCreate, ChatMessageRead, ChatSessionCreate
from app.schemas.common import ApiResponse
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMInvocationError,
    LLMOutputParseError,
)
from app.services.memory.service import MemoryService

router = APIRouter()


@router.post("/projects/{project_id}/chat/sessions", response_model=ApiResponse[dict])
def create_chat_session(
    project_id: str, payload: ChatSessionCreate, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    session = MemoryService(db).create_session(project_id, payload.user_id, payload.title)
    return ApiResponse(data={"id": session.id, "title": session.title, "status": session.status})


@router.get("/projects/{project_id}/chat/sessions", response_model=ApiResponse[list[dict]])
def list_chat_sessions(project_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[dict]]:
    sessions = MemoryService(db).list_sessions(project_id)
    return ApiResponse(
        data=[
            {"id": session.id, "title": session.title, "status": session.status}
            for session in sessions
        ]
    )


@router.post("/chat/sessions/{session_id}/messages", response_model=ApiResponse[ChatAnswer])
def send_chat_message(
    session_id: str, payload: ChatMessageCreate, db: Session = Depends(get_db)
) -> ApiResponse[ChatAnswer]:
    memory_service = MemoryService(db)
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="chat session not found")
    try:
        graph_result = run_chat_graph(db, session, payload.content)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (LLMInvocationError, LLMOutputParseError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Chat/RAG 调用失败：{exc}",
        ) from exc
    rag_answer = graph_result["rag_answer"]
    return ApiResponse(
        data=rag_answer
    )


@router.get("/chat/sessions/{session_id}/messages", response_model=ApiResponse[list[ChatMessageRead]])
def list_chat_messages(session_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[ChatMessageRead]]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return ApiResponse(data=[ChatMessageRead.model_validate(item) for item in messages])
