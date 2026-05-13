from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any
from unittest.mock import patch

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMInvocationError,
    LLMOutputParseError,
)
from app.utils.json_output import extract_json_object


class LangChainLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.settings = get_settings()

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        model_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config, "chat"):
            return self._mock_json(schema_name=schema_name, user_prompt=user_prompt)

        json_system_prompt = (
            f"{system_prompt}\n\n"
            "You must return a single valid JSON object only. "
            "Do not return markdown fences or explanatory text."
        )
        try:
            content = self.chat_text(
                system_prompt=json_system_prompt,
                user_prompt=user_prompt,
                model_config=model_config,
                response_format={"type": "json_object"},
            )
        except LLMInvocationError:
            content = self.chat_text(
                system_prompt=json_system_prompt,
                user_prompt=user_prompt,
                model_config=model_config,
            )
        try:
            return extract_json_object(content)
        except Exception:  # noqa: BLE001
            try:
                repaired = self._repair_json_output(content, schema_name, model_config)
                return extract_json_object(repaired)
            except Exception as repair_exc:  # noqa: BLE001
                raise LLMOutputParseError(content) from repair_exc

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model_config: dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config, "chat"):
            return (
                '{"answer":"mock response","reasoning_summary":"mock reasoning",'
                '"citations":[],"confidence":0.42}'
            )
        config = self._require_config(model_config, "chat")
        try:
            with self._network_environment():
                model = self._chat_model(config)
                kwargs = {"response_format": response_format} if response_format else {}
                response = model.invoke(self._messages(system_prompt, user_prompt), **kwargs)
            return _content_to_text(response.content)
        except Exception as exc:  # noqa: BLE001
            raise LLMInvocationError(f"LangChain chat completion failed: {exc}") from exc

    def chat_text_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model_config: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config, "chat"):
            content = "mock response"
            for index in range(0, len(content), 8):
                yield content[index : index + 8]
            return

        config = self._require_config(model_config, "chat")
        try:
            with self._network_environment():
                model = self._chat_model(config)
                for chunk in model.stream(self._messages(system_prompt, user_prompt)):
                    content = _content_to_text(chunk.content)
                    if content:
                        yield content
        except Exception as exc:  # noqa: BLE001
            raise LLMInvocationError(f"LangChain streaming chat completion failed: {exc}") from exc

    def embed_texts(
        self, texts: list[str], model_config: dict[str, Any] | None = None
    ) -> list[list[float]]:
        if not texts:
            return []
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config, "embedding"):
            return [[float((len(text) % 11) + 1), 0.1, 0.2, 0.3] for text in texts]
        config = self._require_config(model_config, "embedding")
        try:
            with self._network_environment():
                embeddings = OpenAIEmbeddings(
                    model=config["model"],
                    api_key=config.get("api_key") or "unused",
                    base_url=config.get("base_url"),
                    timeout=self.settings.llm_timeout_seconds,
                    check_embedding_ctx_length=False,
                )
                return embeddings.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            raise LLMInvocationError(f"LangChain embedding failed: {exc}") from exc

    def _chat_model(self, config: dict[str, Any]) -> ChatOpenAI:
        return ChatOpenAI(
            model=config["model"],
            api_key=config.get("api_key") or "unused",
            base_url=config.get("base_url"),
            timeout=self.settings.llm_timeout_seconds,
            temperature=0,
        )

    @staticmethod
    def _messages(system_prompt: str, user_prompt: str) -> list[SystemMessage | HumanMessage]:
        return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    def _require_config(self, model_config: dict[str, Any] | None, kind: str) -> dict[str, Any]:
        config = self._select_config(model_config, kind)
        if config is None:
            raise LLMConfigurationError(f"{kind} model configuration is required.")
        if not config.get("model"):
            raise LLMConfigurationError(f"{kind} model is missing in model config.")
        if not (config.get("api_key") or config.get("base_url")):
            raise LLMConfigurationError(f"{kind} api_key or base_url is missing in model config.")
        return config

    @staticmethod
    def _select_config(model_config: dict[str, Any] | None, kind: str) -> dict[str, Any] | None:
        if model_config is None:
            return None
        nested = model_config.get(kind)
        if isinstance(nested, dict):
            return nested

        if kind == "chat" and model_config.get("chat_model"):
            return {
                "provider_type": model_config.get("provider_type", "openai-compatible"),
                "base_url": model_config.get("base_url"),
                "api_key": model_config.get("api_key"),
                "model": model_config.get("chat_model"),
            }
        if kind == "embedding" and model_config.get("embedding_model"):
            return {
                "provider_type": model_config.get("provider_type", "openai-compatible"),
                "base_url": model_config.get("base_url"),
                "api_key": model_config.get("api_key"),
                "model": model_config.get("embedding_model"),
            }
        return None

    def _has_real_provider(self, model_config: dict[str, Any] | None, kind: str) -> bool:
        config = self._select_config(model_config, kind)
        return bool(config and config.get("model") and (config.get("api_key") or config.get("base_url")))

    def _network_environment(self):
        if self.settings.llm_use_env_proxy:
            return nullcontext()
        return _without_proxy_environment()

    def _repair_json_output(
        self,
        broken_content: str,
        schema_name: str,
        model_config: dict[str, Any] | None,
    ) -> str:
        return self.chat_text(
            system_prompt=(
                "You repair malformed JSON returned by another model. "
                "Return one valid JSON object only. Do not add markdown or explanations."
            ),
            user_prompt=(
                f"Target schema name: {schema_name}\n"
                "Repair this malformed JSON-like content into strict JSON:\n"
                f"{broken_content}"
            ),
            model_config=model_config,
            response_format={"type": "json_object"},
        )

    @staticmethod
    def _mock_json(schema_name: str, user_prompt: str) -> dict[str, Any]:
        if schema_name == "ReviewGraphOutput":
            return {
                "summary": "Mock review summary based on fallback provider.",
                "overall_risk": "medium",
                "findings": [
                    {
                        "severity": "medium",
                        "category": "maintainability",
                        "title": "需要补充边界情况说明",
                        "evidence": user_prompt[:120],
                        "impact": "当前实现可读性和约束表达不足。",
                        "suggestion": "补充输入校验并完善函数边界注释。",
                        "example_fix": None,
                    }
                ],
                "suggestions": [{"label": "增加边界测试"}],
                "positive_notes": ["函数结构简单，便于继续扩展。"],
                "uncertain_points": ["未看到完整调用上下文。"],
            }
        if schema_name == "TestPlanOutput":
            return {
                "scenarios": [
                    {"name": "happy path", "case_type": "happy_path", "description": "正常路径"},
                    {"name": "edge case", "case_type": "edge_case", "description": "边界输入"},
                    {"name": "exception case", "case_type": "exception", "description": "异常输入"},
                ]
            }
        if schema_name == "TestCodeOutput":
            return {
                "test_code": "def test_generated_case():\n    assert True\n",
                "self_check_report": {"syntax_ok": True, "mode": "mock"},
            }
        if schema_name == "QueryRewriteOutput":
            return {
                "rewritten_queries": [
                    "实验室编码规范",
                    "历史 review 案例",
                    "项目背景与约定",
                ]
            }
        if schema_name == "RagAnswerOutput":
            return {
                "answer": "当前为 mock RAG 回答，说明知识库链路已接通。",
                "reasoning_summary": "基于检索上下文生成占位答案。",
                "citations": [],
                "confidence": 0.56,
            }
        if schema_name == "MemoryExtractionOutput":
            return {
                "should_store": False,
                "memory_type": "preference",
                "content": "",
                "tags": [],
            }
        return {
            "schema": schema_name,
            "mocked": True,
            "echo": user_prompt[:120],
        }


@contextmanager
def _without_proxy_environment() -> Iterator[None]:
    proxy_keys = {
        key
        for key in os.environ
        if key.upper() in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}
    }
    clean_env = {key: value for key, value in os.environ.items() if key not in proxy_keys}
    with patch.dict(os.environ, clean_env, clear=True):
        yield


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return "" if content is None else str(content)
