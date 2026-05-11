from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        model_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model_config: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def embed_texts(
        self, texts: list[str], model_config: dict[str, Any] | None = None
    ) -> list[list[float]]:
        raise NotImplementedError
