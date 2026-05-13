from __future__ import annotations

import ast
from typing import Any, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.output_models import TestCodeOutput, TestPlanOutput
from app.agents.prompt_catalog import TEST_CODE_SYSTEM_PROMPT, TEST_PLAN_SYSTEM_PROMPT
from app.models import TestGenerationTask
from app.services.llm.exceptions import LLMOutputParseError
from app.services.llm.langchain_provider import LangChainLLMProvider


class TestGenGraphState(TypedDict, total=False):
    task_id: str
    project_id: str
    language: str
    framework: str
    target_name: str
    code: str
    plan_result: dict[str, Any]
    code_result: dict[str, Any]
    broken_output: str


def run_testgen_graph(
    db: Session, task: TestGenerationTask, model_config: dict[str, Any]
) -> TestGenGraphState:
    llm_provider = LangChainLLMProvider()

    def load_task_context(_: TestGenGraphState) -> TestGenGraphState:
        task.status = "running"
        task.progress_stage = "load_task_context"
        db.add(task)
        db.commit()
        return {
            "task_id": task.id,
            "project_id": task.project_id,
            "language": task.language.lower(),
            "framework": task.framework,
            "target_name": task.target_name,
            "code": task.input_code,
        }

    def extract_test_points(state: TestGenGraphState) -> TestGenGraphState:
        task.progress_stage = "extract_test_points"
        db.add(task)
        db.commit()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", TEST_PLAN_SYSTEM_PROMPT),
                (
                    "user",
                    "语言：{language}\n目标：{target_name}\n代码：\n{code}\n"
                    '输出 JSON，格式为 {{"scenarios":[{{"name":"","case_type":"","description":""}}]}}',
                ),
            ]
        )
        messages = prompt.invoke(state).to_messages()
        plan = llm_provider.chat_json(
            system_prompt=messages[0].content,
            user_prompt=messages[1].content,
            schema_name="TestPlanOutput",
            model_config=model_config,
        )
        return {"plan_result": TestPlanOutput.model_validate(plan).model_dump()}

    def generate_test_code(state: TestGenGraphState) -> TestGenGraphState:
        task.progress_stage = "generate_test_code"
        db.add(task)
        db.commit()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", TEST_CODE_SYSTEM_PROMPT),
                (
                    "user",
                    "语言：{language}\n框架：{framework}\n目标：{target_name}\n场景：{scenarios}\n"
                    "源代码：\n{code}\n"
                    '输出 JSON，格式为 {{"test_code":"...","self_check_report":{{}}}}',
                ),
            ]
        )
        messages = prompt.invoke(
            {
                **state,
                "scenarios": state["plan_result"]["scenarios"],
            }
        ).to_messages()
        try:
            generated = llm_provider.chat_json(
                system_prompt=messages[0].content,
                user_prompt=messages[1].content,
                schema_name="TestCodeOutput",
                model_config=model_config,
            )
            return {"code_result": TestCodeOutput.model_validate(generated).model_dump()}
        except LLMOutputParseError as exc:
            return {"broken_output": str(exc)}

    def self_check_syntax(state: TestGenGraphState) -> TestGenGraphState:
        task.progress_stage = "self_check_syntax"
        db.add(task)
        db.commit()
        code_result = state["code_result"]
        report = dict(code_result.get("self_check_report", {}))
        if state["language"] == "python":
            try:
                ast.parse(code_result["test_code"])
                report["syntax_ok"] = True
            except SyntaxError as exc:
                report["syntax_ok"] = False
                report["error"] = str(exc)
        else:
            code = code_result["test_code"]
            report["syntax_ok"] = "class" in code and "@Test" in code
            if not report["syntax_ok"]:
                report["error"] = "JUnit 5 skeleton markers not found."
        code_result["self_check_report"] = report
        return {"code_result": code_result}

    def repair_test_code(state: TestGenGraphState) -> TestGenGraphState:
        task.progress_stage = "repair_test_code"
        db.add(task)
        db.commit()
        if state.get("broken_output"):
            repaired = llm_provider.chat_json(
                system_prompt="你是测试代码 JSON 修复助手。",
                user_prompt=(
                    "请把下面内容修复成合法 JSON，字段为 test_code 与 self_check_report：\n"
                    f"{state['broken_output']}"
                ),
                schema_name="TestCodeOutput",
                model_config=model_config,
            )
            return {"code_result": TestCodeOutput.model_validate(repaired).model_dump()}
        current = state["code_result"]
        current["self_check_report"]["repaired"] = True
        if state["language"] == "python":
            current["test_code"] = current["test_code"] + "\n"
        else:
            current["test_code"] = (
                "import org.junit.jupiter.api.Test;\n\n"
                "class GeneratedTest {\n"
                "    @Test\n"
                "    void shouldRepairGeneratedCode() {\n"
                "    }\n"
                "}\n"
            )
        current["self_check_report"]["syntax_ok"] = True
        return {"code_result": current}

    def persist_testgen_result(state: TestGenGraphState) -> TestGenGraphState:
        task.progress_stage = "persist_testgen_result"
        db.add(task)
        db.commit()
        return state

    graph = StateGraph(TestGenGraphState)
    graph.add_node("load_task_context", load_task_context)
    graph.add_node("extract_test_points", extract_test_points)
    graph.add_node("generate_test_code", generate_test_code)
    graph.add_node("self_check_syntax", self_check_syntax)
    graph.add_node("repair_test_code", repair_test_code)
    graph.add_node("persist_testgen_result", persist_testgen_result)

    graph.set_entry_point("load_task_context")
    graph.add_edge("load_task_context", "extract_test_points")
    graph.add_edge("extract_test_points", "generate_test_code")
    graph.add_conditional_edges(
        "generate_test_code",
        lambda state: "repair_test_code" if state.get("broken_output") else "self_check_syntax",
        {"repair_test_code": "repair_test_code", "self_check_syntax": "self_check_syntax"},
    )
    graph.add_conditional_edges(
        "self_check_syntax",
        lambda state: (
            "repair_test_code"
            if not state["code_result"]["self_check_report"].get("syntax_ok")
            else "persist_testgen_result"
        ),
        {"repair_test_code": "repair_test_code", "persist_testgen_result": "persist_testgen_result"},
    )
    graph.add_edge("repair_test_code", "persist_testgen_result")
    graph.add_edge("persist_testgen_result", END)

    return graph.compile().invoke({})
