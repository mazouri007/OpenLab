from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.prompt_catalog import COMMIT_QA_PROMPT
from app.models import ChatSession, Project
from app.schemas.chat import ChatAnswer, ChatMessageCreate
from app.schemas.review import ReviewRequest
from app.services.commit_context.service import CommitContext, CommitContextService
from app.services.github.context_detection import (
    GitHubContextInference,
    build_github_clarification_answer,
    infer_github_context,
)
from app.services.memory.service import MemoryService
from app.services.rag.service import RagService
from app.services.review.service import ReviewService


class ChatGraphState(TypedDict, total=False):
    session_id: str
    user_message: str
    context_type: str
    intent: str
    github_inference: GitHubContextInference
    clarification_answer: ChatAnswer
    commit_context: CommitContext
    short_term_summary: str
    used_memory: list[str]
    rag_answer: ChatAnswer


def run_chat_graph(
    db: Session, session: ChatSession, payload: ChatMessageCreate | str
) -> ChatGraphState:
    request = payload if isinstance(payload, ChatMessageCreate) else ChatMessageCreate(content=payload)
    question = request.content
    inferred_context = (
        infer_github_context(db, session.project_id, question)
        if request.context_type == "general"
        else GitHubContextInference(
            needs_github_context=True,
            repository_id=request.repository_id,
            commit_sha=request.commit_sha,
        )
    )
    effective_request = _effective_commit_request(request, inferred_context)
    clarification_answer = (
        _build_clarification_chat_answer(inferred_context)
        if request.context_type == "general" and inferred_context.needs_clarification
        else None
    )
    memory_service = MemoryService(db)
    rag_service = RagService(db)

    def load_session_context(_: ChatGraphState) -> ChatGraphState:
        state: ChatGraphState = {
            "session_id": session.id,
            "user_message": question,
            "context_type": effective_request.context_type,
            "intent": _resolve_commit_intent(effective_request.intent, question),
            "github_inference": inferred_context,
        }
        if clarification_answer:
            state["clarification_answer"] = clarification_answer
        return state

    def load_commit_context(state: ChatGraphState) -> ChatGraphState:
        if state.get("clarification_answer") or effective_request.context_type != "github_commit":
            return state
        context = CommitContextService(db).load_commit_context(
            project_id=session.project_id,
            repository_id=effective_request.repository_id or "",
            commit_sha=effective_request.commit_sha or "",
        )
        return {**state, "commit_context": context}

    def recall_memory(_: ChatGraphState) -> ChatGraphState:
        summary = memory_service.get_latest_summary(session.id)
        memories = memory_service.recall_long_term_memory(session.project_id, question)
        return {
            "short_term_summary": summary,
            "used_memory": [item.content for item in memories],
        }

    def run_rag(state: ChatGraphState) -> ChatGraphState:
        if state.get("clarification_answer"):
            return {"rag_answer": state["clarification_answer"]}

        commit_context = state.get("commit_context")
        if commit_context:
            answer = _answer_commit_question(
                db=db,
                session=session,
                question=question,
                request=effective_request,
                intent=state.get("intent", "explain"),
                commit_context=commit_context,
                rag_service=rag_service,
                short_term_summary=state.get("short_term_summary", ""),
                used_memory=state.get("used_memory", []),
            )
            return {"rag_answer": answer}

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
    graph.add_node("load_commit_context", load_commit_context)
    graph.add_node("recall_memory", recall_memory)
    graph.add_node("run_rag", run_rag)
    graph.add_node("persist_messages", persist_messages)
    graph.set_entry_point("load_session_context")
    graph.add_edge("load_session_context", "load_commit_context")
    graph.add_edge("load_commit_context", "recall_memory")
    graph.add_edge("recall_memory", "run_rag")
    graph.add_edge("run_rag", "persist_messages")
    graph.add_edge("persist_messages", END)
    return graph.compile().invoke({})


def _effective_commit_request(
    request: ChatMessageCreate, inference: GitHubContextInference
) -> ChatMessageCreate:
    if request.context_type == "github_commit" or not inference.is_complete_commit_context:
        return request
    return ChatMessageCreate(
        content=request.content,
        context_type="github_commit",
        repository_id=inference.repository_id,
        commit_sha=inference.commit_sha,
        intent=request.intent,
        persist_review=request.persist_review,
    )


def _build_clarification_chat_answer(inference: GitHubContextInference) -> ChatAnswer:
    metadata: dict[str, Any] = {
        "context_type": "github_commit",
        "needs_clarification": True,
        "missing_fields": inference.missing_fields,
        "reason": inference.reason,
    }
    if inference.repo_full_name:
        metadata["repo_full_name"] = inference.repo_full_name
    if inference.commit_sha:
        metadata["commit_sha"] = inference.commit_sha
    if inference.pr_number is not None:
        metadata["pr_number"] = inference.pr_number
    return ChatAnswer(
        answer=build_github_clarification_answer(inference),
        citations=[],
        used_memory=[],
        used_documents=[],
        rewritten_queries=[],
        reasoning_summary="检测到 GitHub 仓库线索，但缺少仓库或 commit SHA，未调用 GitHub MCP。",
        confidence=0.0,
        metadata=metadata,
    )


def _answer_commit_question(
    db: Session,
    session: ChatSession,
    question: str,
    request: ChatMessageCreate,
    intent: str,
    commit_context: CommitContext,
    rag_service: RagService,
    short_term_summary: str,
    used_memory: list[str],
) -> ChatAnswer:
    metadata: dict[str, Any] = {
        "context_type": "github_commit",
        "repo_full_name": commit_context.repo_full_name,
        "commit_sha": commit_context.commit_sha,
        "intent": intent,
        "truncated": commit_context.truncated,
        "context_provider": commit_context.source_provider,
    }
    if intent in {"review", "compliance"} and request.persist_review:
        return _run_persisted_commit_review(
            db=db,
            session=session,
            request=request,
            question=question,
            intent=intent,
            commit_context=commit_context,
            metadata=metadata,
        )
    return rag_service.answer(
        project_id=session.project_id,
        question=_commit_question_for_intent(question, intent),
        short_term_summary=short_term_summary,
        long_term_memory=used_memory,
        extra_context=commit_context.to_question_context(),
        extra_citations=commit_context.citations(),
        metadata=metadata,
        system_prompt=COMMIT_QA_PROMPT,
    )


def _run_persisted_commit_review(
    db: Session,
    session: ChatSession,
    request: ChatMessageCreate,
    question: str,
    intent: str,
    commit_context: CommitContext,
    metadata: dict[str, Any],
) -> ChatAnswer:
    review_payload = ReviewRequest(
        title=f"Commit {commit_context.commit_sha[:12]} {intent}",
        source_type="github_commit",
        language=_project_language(db, session.project_id),
        repository_id=request.repository_id,
        commit_sha=request.commit_sha,
        content=question,
    )
    service = ReviewService(db)
    task = service.create_task(session.project_id, session.user_id, review_payload)
    result = service.run_task(task)
    metadata["review_task_id"] = task.id
    raw_output = result.raw_output_json or {}
    citations = commit_context.citations()
    answer = _render_review_answer(raw_output)
    return ChatAnswer(
        answer=answer,
        citations=citations,
        used_memory=[],
        used_documents=[str(item.get("source_title") or item.get("chunk_id")) for item in citations],
        rewritten_queries=[question, f"{intent} {commit_context.repo_full_name} {commit_context.commit_sha}"],
        reasoning_summary=(
            "基于 GitHub MCP 返回的 commit diff、项目审查提示词和知识库规范生成结构化审查。"
        ),
        confidence=0.82,
        metadata=metadata,
    )


def _render_review_answer(raw_output: dict[str, Any]) -> str:
    lines = [
        "### 审查结论",
        str(raw_output.get("summary") or "暂无审查摘要。"),
        "",
        f"风险等级：{raw_output.get('overall_risk', 'medium')}",
    ]
    findings = raw_output.get("findings") or []
    if findings:
        lines.extend(["", "### 问题发现"])
        for item in findings:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- [{item.get('severity', 'info')}] {item.get('title', '未命名问题')}："
                f"{item.get('impact', '未说明影响')}"
            )
            if item.get("evidence"):
                lines.append(f"  证据：{item['evidence']}")
            if item.get("suggestion"):
                lines.append(f"  建议：{item['suggestion']}")
    positive_notes = raw_output.get("positive_notes") or []
    if positive_notes:
        lines.extend(["", "### 正向观察", *[f"- {item}" for item in positive_notes]])
    uncertain_points = raw_output.get("uncertain_points") or []
    if uncertain_points:
        lines.extend(["", "### 不确定点", *[f"- {item}" for item in uncertain_points]])
    return "\n".join(lines)


def _resolve_commit_intent(intent: str, question: str) -> str:
    if intent != "auto":
        return intent
    normalized = question.lower()
    if any(token in normalized for token in ["审查", "review", "风险", "bug", "缺陷"]):
        return "review"
    if any(token in normalized for token in ["规范", "符合", "compliance", "标准"]):
        return "compliance"
    return "explain"


def _commit_question_for_intent(question: str, intent: str) -> str:
    if intent == "explain":
        return f"{question}\n请重点说明这个 commit 增加或改变了什么功能。"
    if intent == "compliance":
        return f"{question}\n请重点判断这个 commit 是否符合项目规范，并列出证据。"
    if intent == "review":
        return f"{question}\n请按代码审查视角列出风险、证据、影响和建议。"
    return question


def _project_language(db: Session, project_id: str) -> str:
    project = db.get(Project, project_id)
    return project.primary_language if project else "python"
