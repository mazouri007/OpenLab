from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any
from unittest.mock import patch

import httpx
from litellm import completion, embedding

from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.exceptions import (
    LLMConfigurationError,
    LLMInvocationError,
    LLMOutputParseError,
)
from app.utils.json_output import extract_json_object


class LiteLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.settings = get_settings()

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        model_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config):
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
        except Exception as exc:  # noqa: BLE001
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
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config):
            return (
                '{"answer":"mock response","reasoning_summary":"mock reasoning",'
                '"citations":[],"confidence":0.42}'
            )
        config = self._require_config(model_config)
        litellm_error: Exception | None = None
        try:
            with self._network_environment():
                response = completion(
                    model=config["chat_model"],
                    api_key=config.get("api_key"),
                    base_url=config.get("base_url"),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=response_format,
                    timeout=self.settings.llm_timeout_seconds,
                )
            return response["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            litellm_error = exc

        if config.get("provider_type") == "openai-compatible":
            try:
                return self._chat_text_openai_compatible(
                    system_prompt, user_prompt, config, response_format=response_format
                )
            except Exception as exc:  # noqa: BLE001
                raise LLMInvocationError(
                    "LiteLLM completion failed, and direct OpenAI-Compatible fallback "
                    f"also failed. LiteLLM error: {litellm_error}. Direct error: {exc}"
                ) from exc

        raise LLMInvocationError(f"LiteLLM completion failed: {litellm_error}") from litellm_error

    def embed_texts(
        self, texts: list[str], model_config: dict[str, Any] | None = None
    ) -> list[list[float]]:
        if self.settings.enable_mock_llm and not self._has_real_provider(model_config):
            return [[float((len(text) % 11) + 1), 0.1, 0.2, 0.3] for text in texts]
        config = self._require_config(model_config)
        litellm_error: Exception | None = None
        try:
            with self._network_environment():
                response = embedding(
                    model=config["embedding_model"],
                    input=texts,
                    api_key=config.get("api_key"),
                    base_url=config.get("base_url"),
                    timeout=self.settings.llm_timeout_seconds,
                )
            return [item["embedding"] for item in response["data"]]
        except Exception as exc:  # noqa: BLE001
            litellm_error = exc

        if config.get("provider_type") == "openai-compatible":
            try:
                return self._embed_texts_openai_compatible(texts, config)
            except Exception as exc:  # noqa: BLE001
                raise LLMInvocationError(
                    "LiteLLM embedding failed, and direct OpenAI-Compatible fallback "
                    f"also failed. LiteLLM error: {litellm_error}. Direct error: {exc}"
                ) from exc

        raise LLMInvocationError(f"LiteLLM embedding failed: {litellm_error}") from litellm_error

    def _require_config(self, model_config: dict[str, Any] | None) -> dict[str, Any]:
        if model_config is None:
            raise LLMConfigurationError("Model configuration is required.")
        if not model_config.get("chat_model"):
            raise LLMConfigurationError("chat_model is missing in model config.")
        return model_config

    @staticmethod
    def _has_real_provider(model_config: dict[str, Any] | None) -> bool:
        return bool(
            model_config
            and model_config.get("chat_model")
            and (model_config.get("api_key") or model_config.get("base_url"))
        )

    def _network_environment(self):
        if self.settings.llm_use_env_proxy:
            return nullcontext()
        return _without_proxy_environment()

    def _chat_text_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        config: dict[str, Any],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": _strip_litellm_openai_prefix(config["chat_model"]),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = _post_openai_compatible(
            base_url=config.get("base_url"),
            api_key=config.get("api_key"),
            endpoint="chat/completions",
            payload=payload,
            timeout=self.settings.llm_timeout_seconds,
        )
        return response["choices"][0]["message"]["content"]

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

    def _embed_texts_openai_compatible(
        self, texts: list[str], config: dict[str, Any]
    ) -> list[list[float]]:
        response = _post_openai_compatible(
            base_url=config.get("base_url"),
            api_key=config.get("api_key"),
            endpoint="embeddings",
            payload={
                "model": _strip_litellm_openai_prefix(config["embedding_model"]),
                "input": texts,
            },
            timeout=self.settings.llm_timeout_seconds,
        )
        return [item["embedding"] for item in response["data"]]

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


def _strip_litellm_openai_prefix(model: str) -> str:
    return model.removeprefix("openai/")


def _post_openai_compatible(
    base_url: str | None,
    api_key: str | None,
    endpoint: str,
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    if not base_url:
        raise LLMConfigurationError("base_url is missing in model config.")
    if not api_key:
        raise LLMConfigurationError("api_key is missing in model config.")

    url = _build_openai_compatible_url(base_url, endpoint)
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500]
        raise LLMInvocationError(
            f"OpenAI-Compatible endpoint returned HTTP {exc.response.status_code}: {body}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LLMInvocationError(f"OpenAI-Compatible connection failed: {exc}") from exc


def _build_openai_compatible_url(base_url: str, endpoint: str) -> str:
    normalized = base_url.strip().rstrip("/")
    endpoint = endpoint.strip("/")
    if normalized.endswith(f"/{endpoint}"):
        return normalized
    return f"{normalized}/{endpoint}"
