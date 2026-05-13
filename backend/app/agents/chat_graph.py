from __future__ import annotations

from collections.abc import Generator
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.prompt_catalog import COMMIT_QA_PROMPT
from app.models import ChatSession, Project
from app.schemas.chat import ChatAnswer, ChatMessageCreate
from app.schemas.review import ReviewRequest
from app.schemas.testgen import TestGenerationRequest
from app.services.chat_intent import ChatIntent, detect_chat_intent
from app.services.code_context.models import (
    CodeChangeContext,
    framework_for_language,
    language_for_path,
)
from app.services.code_context.resolver import CodeContextResolution, CodeContextResolver
from app.services.memory.service import MemoryService
from app.services.rag.service import RagService
from app.services.review.service import ReviewService
from app.services.testgen.service import TestGenerationService

ChatStreamEvent = tuple[str, dict[str, Any]]


class ChatGraphState(TypedDict, total=False):
    session_id: str
    user_message: str
    intent: ChatIntent
    context_resolution: CodeContextResolution
    short_term_summary: str
    used_memory: list[str]
    rag_answer: ChatAnswer


def run_chat_graph(
    db: Session, session: ChatSession, payload: ChatMessageCreate | str
) -> ChatGraphState:
    request = payload if isinstance(payload, ChatMessageCreate) else ChatMessageCreate(content=payload)
    question = request.content
    memory_service = MemoryService(db)
    rag_service = RagService(db)

    def detect_intent(_: ChatGraphState) -> ChatGraphState:
        intent = detect_chat_intent(request.action, question)
        return {"session_id": session.id, "user_message": question, "intent": intent}

    def resolve_code_context(state: ChatGraphState) -> ChatGraphState:
        intent = state["intent"]
        needs_code_context = intent.action in {"review", "test", "review_and_test"}
        resolution = CodeContextResolver(db).resolve(
            project_id=session.project_id,
            request=request,
            needs_code_context=needs_code_context,
        )
        return {"context_resolution": resolution}

    def recall_memory(_: ChatGraphState) -> ChatGraphState:
        summary = memory_service.get_latest_summary(session.id)
        memories = memory_service.recall_long_term_memory(session.project_id, question)
        return {
            "short_term_summary": summary,
            "used_memory": [item.content for item in memories],
        }

    def run_assistant(state: ChatGraphState) -> ChatGraphState:
        intent = state["intent"]
        resolution = state["context_resolution"]
        if resolution.needs_clarification:
            return {"rag_answer": _build_code_context_clarification(intent, resolution)}

        code_context = resolution.context
        if code_context and intent.action in {"review", "test", "review_and_test"}:
            return {
                "rag_answer": _execute_code_actions(
                    db=db,
                    session=session,
                    request=request,
                    question=question,
                    intent=intent,
                    code_context=code_context,
                    resolution=resolution,
                )
            }

        if code_context:
            answer = rag_service.answer(
                project_id=session.project_id,
                question=question,
                short_term_summary=state.get("short_term_summary", ""),
                long_term_memory=state.get("used_memory", []),
                extra_context=code_context.to_review_input(),
                extra_citations=code_context.citations(),
                metadata=_base_metadata(intent, code_context),
                system_prompt=COMMIT_QA_PROMPT,
            )
            return {"rag_answer": answer}

        answer = rag_service.answer(
            project_id=session.project_id,
            question=question,
            short_term_summary=state.get("short_term_summary", ""),
            long_term_memory=state.get("used_memory", []),
            metadata={"detected_action": intent.action, "intent_reason": intent.reason},
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
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("resolve_code_context", resolve_code_context)
    graph.add_node("recall_memory", recall_memory)
    graph.add_node("run_assistant", run_assistant)
    graph.add_node("persist_messages", persist_messages)
    graph.set_entry_point("detect_intent")
    graph.add_edge("detect_intent", "resolve_code_context")
    graph.add_edge("resolve_code_context", "recall_memory")
    graph.add_edge("recall_memory", "run_assistant")
    graph.add_edge("run_assistant", "persist_messages")
    graph.add_edge("persist_messages", END)
    return graph.compile().invoke({})


def stream_chat_graph(
    db: Session, session: ChatSession, payload: ChatMessageCreate | str
) -> Generator[ChatStreamEvent, None, ChatAnswer]:
    request = payload if isinstance(payload, ChatMessageCreate) else ChatMessageCreate(content=payload)
    question = request.content
    memory_service = MemoryService(db)
    rag_service = RagService(db)

    yield ("status", {"stage": "recall", "message": "正在识别意图并读取会话记忆"})
    intent = detect_chat_intent(request.action, question)
    resolution = CodeContextResolver(db).resolve(
        project_id=session.project_id,
        request=request,
        needs_code_context=intent.action in {"review", "test", "review_and_test"},
    )
    short_term_summary = memory_service.get_latest_summary(session.id)
    used_memory = [
        item.content for item in memory_service.recall_long_term_memory(session.project_id, question)
    ]

    if resolution.needs_clarification:
        answer = _build_code_context_clarification(intent, resolution)
        yield ("status", {"stage": "generate", "message": "正在生成上下文补充提示"})
        yield from _delta_events(answer.answer)
    elif resolution.context and intent.action in {"review", "test", "review_and_test"}:
        yield ("status", {"stage": "generate", "message": "正在执行代码审查或测试生成"})
        answer = _execute_code_actions(
            db=db,
            session=session,
            request=request,
            question=question,
            intent=intent,
            code_context=resolution.context,
            resolution=resolution,
        )
        yield from _delta_events(answer.answer)
    elif resolution.context:
        answer = yield from rag_service.stream_answer(
            project_id=session.project_id,
            question=question,
            short_term_summary=short_term_summary,
            long_term_memory=used_memory,
            extra_context=resolution.context.to_review_input(),
            extra_citations=resolution.context.citations(),
            metadata=_base_metadata(intent, resolution.context),
            system_prompt=COMMIT_QA_PROMPT,
        )
    else:
        answer = yield from rag_service.stream_answer(
            project_id=session.project_id,
            question=question,
            short_term_summary=short_term_summary,
            long_term_memory=used_memory,
            metadata={"detected_action": intent.action, "intent_reason": intent.reason},
        )

    yield ("status", {"stage": "persist", "message": "正在保存会话消息"})
    memory_service.append_message(session.id, "user", question)
    assistant_message = memory_service.append_message(
        session.id,
        "assistant",
        answer.answer,
        citations=answer.citations,
    )
    yield (
        "done",
        {
            "answer": answer.model_dump(),
            "assistant_message_id": assistant_message.id,
        },
    )
    return answer


def _execute_code_actions(
    db: Session,
    session: ChatSession,
    request: ChatMessageCreate,
    question: str,
    intent: ChatIntent,
    code_context: CodeChangeContext,
    resolution: CodeContextResolution,
) -> ChatAnswer:
    metadata = _base_metadata(intent, code_context)
    answer_sections = []
    citations = code_context.citations()

    if intent.action in {"review", "review_and_test"}:
        review_result = _run_review_from_context(db, session, question, code_context)
        metadata["review_task_id"] = review_result["task_id"]
        answer_sections.append(_render_review_answer(review_result))

    if intent.action in {"test", "review_and_test"}:
        test_result = _run_testgen_from_context(db, session, request, question, code_context, resolution)
        metadata.update(test_result["metadata"])
        answer_sections.append(test_result["answer"])

    return ChatAnswer(
        answer="\n\n".join(section for section in answer_sections if section),
        citations=citations,
        used_memory=[],
        used_documents=[str(item.get("source_title") or item.get("chunk_id")) for item in citations],
        rewritten_queries=[question],
        reasoning_summary="根据聊天意图自动调用代码审查和/或测试生成工具，并把结果汇总为回答。",
        confidence=0.86,
        metadata=metadata,
    )


def _run_review_from_context(
    db: Session, session: ChatSession, question: str, code_context: CodeChangeContext
) -> dict[str, Any]:
    payload = ReviewRequest(
        title=f"{code_context.title} review",
        source_type="manual_diff",
        language=_project_language(db, session.project_id),
        content=f"{question}\n\n{code_context.to_review_input()}",
    )
    service = ReviewService(db)
    task = service.create_task(session.project_id, session.user_id, payload)
    result = service.run_task(task)
    return {"task_id": task.id, "raw_output": result.raw_output_json or {}}


def _run_testgen_from_context(
    db: Session,
    session: ChatSession,
    request: ChatMessageCreate,
    question: str,
    code_context: CodeChangeContext,
    resolution: CodeContextResolution,
) -> dict[str, Any]:
    preferred_paths = resolution.inference.file_paths if resolution.inference else []
    target_file = code_context.supported_test_file(preferred_paths)
    if target_file is None:
        return {
            "answer": (
                "### 测试生成\n"
                "暂未找到可生成测试的 Python 或 Java 变更文件。请指定 `.py` 或 `.java` 文件，"
                "或粘贴对应源代码/diff。"
            ),
            "metadata": {
                "unsupported_reason": "no_supported_test_target",
                "test_generation_task_id": None,
            },
        }

    language = (request.language or language_for_path(target_file.path) or "").lower()
    if language not in {"python", "java"}:
        return {
            "answer": (
                "### 测试生成\n"
                f"当前只支持 python/pytest 和 java/JUnit 5，无法为 `{target_file.path}` "
                f"使用语言 `{language or 'unknown'}` 生成测试。"
            ),
            "metadata": {
                "unsupported_reason": "unsupported_language",
                "test_generation_task_id": None,
            },
        }

    framework = request.framework or framework_for_language(language)
    code = target_file.content_excerpt or target_file.patch or code_context.to_review_input()
    payload = TestGenerationRequest(
        language=language,  # type: ignore[arg-type]
        framework=framework,
        target_name=target_file.path or code_context.title,
        code=code,
        extra_requirements=question,
    )
    service = TestGenerationService(db)
    task = service.create_task(session.project_id, session.user_id, payload)
    result = service.run_task(task)
    return {
        "answer": _render_testgen_answer(task.id, result.raw_output_json or {}, result.test_code),
        "metadata": {
            "test_generation_task_id": task.id,
            "test_target": target_file.path,
            "test_language": language,
            "test_framework": framework,
        },
    }


def _build_code_context_clarification(
    intent: ChatIntent, resolution: CodeContextResolution
) -> ChatAnswer:
    missing = "、".join(resolution.missing_fields) or "代码上下文"
    unsupported = resolution.unsupported_reason
    answer = (
        f"我识别到你想执行 `{intent.action}`，但还缺少：{missing}。"
        if not unsupported
        else f"我识别到你想执行 `{intent.action}`，但当前不支持：{unsupported}。"
    )
    answer += "\n\n你可以补充仓库 + PR 编号、仓库 + commit SHA，或直接粘贴 diff。"
    metadata: dict[str, Any] = {
        "detected_action": intent.action,
        "intent_reason": intent.reason,
        "missing_fields": resolution.missing_fields,
        "needs_clarification": True,
    }
    if unsupported:
        metadata["unsupported_reason"] = unsupported
    return ChatAnswer(
        answer=answer,
        citations=[],
        used_memory=[],
        used_documents=[],
        rewritten_queries=[],
        reasoning_summary="检测到工具型请求，但上下文不足，未执行审查或测试生成。",
        confidence=0.0,
        metadata=metadata,
    )


def _base_metadata(intent: ChatIntent, code_context: CodeChangeContext) -> dict[str, Any]:
    return {
        "detected_action": intent.action,
        "intent_reason": intent.reason,
        "context_kind": code_context.kind,
        "repo_full_name": code_context.repo_full_name,
        "commit_sha": code_context.commit_sha,
        "pr_number": code_context.pr_number,
        "context_provider": code_context.source_provider,
    }


def _render_review_answer(review_result: dict[str, Any]) -> str:
    raw_output = review_result["raw_output"]
    lines = [
        "### 代码审查",
        f"Review 任务 ID：`{review_result['task_id']}`",
        "",
        str(raw_output.get("summary") or "暂无审查摘要。"),
        "",
        f"风险等级：{raw_output.get('overall_risk', 'medium')}",
    ]
    findings = raw_output.get("findings") or []
    if findings:
        lines.extend(["", "问题发现："])
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
    return "\n".join(lines)


def _render_testgen_answer(task_id: str, raw_output: dict[str, Any], test_code: str) -> str:
    scenarios = (raw_output.get("plan_result") or {}).get("scenarios") or []
    lines = ["### 测试生成", f"TestGeneration 任务 ID：`{task_id}`"]
    if scenarios:
        lines.extend(["", "覆盖场景："])
        for item in scenarios:
            if isinstance(item, dict):
                lines.append(
                    f"- [{item.get('case_type', 'case')}] {item.get('name', '未命名')}："
                    f"{item.get('description', '')}"
                )
    lines.extend(["", "生成的测试代码：", "```", test_code.strip(), "```"])
    return "\n".join(lines)


def _project_language(db: Session, project_id: str) -> str:
    project = db.get(Project, project_id)
    return project.primary_language if project else "python"


def _delta_events(content: str) -> Generator[ChatStreamEvent, None, None]:
    if not content:
        return
    for index in range(0, len(content), 48):
        yield ("delta", {"content": content[index : index + 48]})
