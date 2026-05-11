from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.output_models import ReviewGraphOutput
from app.agents.prompt_catalog import (
    LANGUAGE_CHECKLISTS,
    REVIEW_REPAIR_PROMPT,
    REVIEW_SYSTEM_PROMPT,
)
from app.integrations.github.client import GithubClient
from app.models import (
    CodeReviewTask,
    GithubIntegration,
    GithubRepository,
    KnowledgeChunk,
    PromptTemplate,
)
from app.services.llm.exceptions import LLMOutputParseError
from app.services.llm.litellm_provider import LiteLLMProvider


class ReviewGraphState(TypedDict, total=False):
    task_id: str
    project_id: str
    title: str
    language: str
    source_type: str
    raw_input: dict[str, Any]
    normalized_content: str
    source_files: list[str]
    retrieved_context: list[dict[str, Any]]
    review_prompt: str
    result: dict[str, Any]
    broken_output: str
    model_name: str


def run_review_graph(
    db: Session, task: CodeReviewTask, model_config: dict[str, Any]
) -> ReviewGraphState:
    llm_provider = LiteLLMProvider()

    def load_task_context(_: ReviewGraphState) -> ReviewGraphState:
        task.progress_stage = "load_task_context"
        db.add(task)
        db.commit()
        return {
            "task_id": task.id,
            "project_id": task.project_id,
            "title": task.title,
            "language": task.language.lower(),
            "source_type": task.source_type,
            "raw_input": task.input_payload_json,
            "model_name": model_config["chat_model"],
        }

    def normalize_source(state: ReviewGraphState) -> ReviewGraphState:
        task.progress_stage = "normalize_source"
        db.add(task)
        db.commit()
        raw_input = state["raw_input"]
        source_type = state["source_type"]
        if source_type in {"snippet", "manual_diff", "file_upload"}:
            content = raw_input.get("content") or ""
            return {"normalized_content": content, "source_files": []}

        repo = db.get(GithubRepository, raw_input.get("repository_id") or "")
        integration = (
            db.query(GithubIntegration)
            .filter(GithubIntegration.project_id == task.project_id)
            .first()
        )
        github_client = GithubClient(token=integration.encrypted_token if integration else "")
        if repo is None:
            return {"normalized_content": raw_input.get("content") or "", "source_files": []}
        if source_type == "github_pr":
            diff = github_client.fetch_pull_request_diff(repo.repo_full_name, raw_input.get("pr_number"))
        else:
            diff = github_client.fetch_commit_diff(repo.repo_full_name, raw_input.get("commit_sha"))
        files = [item["path"] for item in diff["files"]]
        content = "\n\n".join(
            f"FILE: {item['path']}\nPATCH:\n{item.get('patch', '')}" for item in diff["files"]
        )
        return {"normalized_content": content, "source_files": files}

    def retrieve_review_context(state: ReviewGraphState) -> ReviewGraphState:
        task.progress_stage = "retrieve_review_context"
        db.add(task)
        db.commit()
        prompt_template = (
            db.query(PromptTemplate)
            .filter(PromptTemplate.project_id == task.project_id)
            .filter(PromptTemplate.template_type == "review")
            .order_by(PromptTemplate.is_default.desc(), PromptTemplate.created_at.desc())
            .first()
        )
        knowledge_chunks = (
            db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.project_id == task.project_id)
            .limit(4)
            .all()
        )
        retrieved = [
            {
                "chunk_id": chunk.id,
                "content": chunk.content[:300],
                "source_title": chunk.metadata_json.get("title"),
            }
            for chunk in knowledge_chunks
        ]
        checklist = LANGUAGE_CHECKLISTS.get(state["language"], LANGUAGE_CHECKLISTS["python"])
        review_prompt = prompt_template.system_prompt if prompt_template else REVIEW_SYSTEM_PROMPT
        return {
            "retrieved_context": retrieved,
            "review_prompt": review_prompt + "\n" + "\n".join(f"- {item}" for item in checklist),
        }

    def invoke_review_model(state: ReviewGraphState) -> ReviewGraphState:
        task.progress_stage = "invoke_review_model"
        task.status = "running"
        db.add(task)
        db.commit()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                (
                    "user",
                    (
                        "任务标题：{title}\n"
                        "语言：{language}\n"
                        "来源：{source_type}\n"
                        "知识库上下文：{retrieved_context}\n"
                        "代码内容：\n{normalized_content}\n\n"
                        "请输出 JSON，包含 summary、overall_risk、findings、suggestions、"
                        "positive_notes、uncertain_points。"
                    ),
                ),
            ]
        )
        rendered = prompt.invoke(
            {
                "system_prompt": state["review_prompt"],
                "title": state["title"],
                "language": state["language"],
                "source_type": state["source_type"],
                "retrieved_context": state["retrieved_context"],
                "normalized_content": state["normalized_content"],
            }
        )
        messages = rendered.to_messages()
        try:
            result = llm_provider.chat_json(
                system_prompt=messages[0].content,
                user_prompt=messages[1].content,
                schema_name="ReviewGraphOutput",
                model_config=model_config,
            )
            return {"result": result}
        except LLMOutputParseError as exc:
            return {"broken_output": str(exc)}

    def repair_review_json(state: ReviewGraphState) -> ReviewGraphState:
        if not state.get("broken_output"):
            return {}
        task.progress_stage = "repair_review_json"
        db.add(task)
        db.commit()
        repaired = llm_provider.chat_json(
            system_prompt="你是 JSON 修复助手。",
            user_prompt=REVIEW_REPAIR_PROMPT.format(
                schema_name="ReviewGraphOutput",
                broken_content=state["broken_output"],
            ),
            schema_name="ReviewGraphOutput",
            model_config=model_config,
        )
        return {"result": repaired}

    def persist_review_result(state: ReviewGraphState) -> ReviewGraphState:
        task.progress_stage = "persist_review_result"
        db.add(task)
        db.commit()
        result_model = ReviewGraphOutput.model_validate(state["result"])
        return {
            "result": {
                **result_model.model_dump(),
                "overall_score": max(0.0, 100.0 - 12.5 * len(result_model.findings)),
                "model_name": state["model_name"],
                "source_files": state.get("source_files", []),
                "used_documents": [item["chunk_id"] for item in state.get("retrieved_context", [])],
            }
        }

    graph = StateGraph(ReviewGraphState)
    graph.add_node("load_task_context", load_task_context)
    graph.add_node("normalize_source", normalize_source)
    graph.add_node("retrieve_review_context", retrieve_review_context)
    graph.add_node("invoke_review_model", invoke_review_model)
    graph.add_node("repair_review_json", repair_review_json)
    graph.add_node("persist_review_result", persist_review_result)

    graph.set_entry_point("load_task_context")
    graph.add_edge("load_task_context", "normalize_source")
    graph.add_edge("normalize_source", "retrieve_review_context")
    graph.add_edge("retrieve_review_context", "invoke_review_model")
    graph.add_conditional_edges(
        "invoke_review_model",
        lambda state: "repair_review_json" if state.get("broken_output") else "persist_review_result",
        {"repair_review_json": "repair_review_json", "persist_review_result": "persist_review_result"},
    )
    graph.add_edge("repair_review_json", "persist_review_result")
    graph.add_edge("persist_review_result", END)

    return graph.compile().invoke({})
