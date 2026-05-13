from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import secrets as secrets_module
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.models import ModelProvider
from app.services.llm.langchain_provider import LangChainLLMProvider
import app.services.llm.langchain_provider as langchain_provider_module
from app.services.llm.provider_resolver import resolve_model_config


def _session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_resolve_model_config_uses_independent_embedding_provider() -> None:
    session_factory = _session_factory()
    with session_factory() as db:
        provider = ModelProvider(
            project_id="project-1",
            name="split provider",
            provider_type="openai-compatible",
            base_url="https://chat.example/v1",
            api_key="chat-key",
            default_chat_model="chat-model",
            default_embedding_model="embed-model",
            embedding_provider_type="openai-compatible",
            embedding_base_url="https://embed.example/v1",
            embedding_api_key="embed-key",
            is_default=True,
        )
        db.add(provider)
        db.commit()

        config = resolve_model_config(db, "project-1")

    assert config["chat"]["base_url"] == "https://chat.example/v1"
    assert config["chat"]["api_key"] == "chat-key"
    assert config["chat"]["model"] == "chat-model"
    assert config["embedding"]["base_url"] == "https://embed.example/v1"
    assert config["embedding"]["api_key"] == "embed-key"
    assert config["embedding"]["model"] == "embed-model"


def test_resolve_model_config_falls_back_to_chat_provider_for_embedding() -> None:
    session_factory = _session_factory()
    with session_factory() as db:
        provider = ModelProvider(
            project_id="project-1",
            name="legacy provider",
            provider_type="openai-compatible",
            base_url="https://chat.example/v1",
            api_key="chat-key",
            default_chat_model="chat-model",
            default_embedding_model="embed-model",
            is_default=True,
        )
        db.add(provider)
        db.commit()

        config = resolve_model_config(db, "project-1")

    assert config["embedding"]["provider_type"] == "openai-compatible"
    assert config["embedding"]["base_url"] == "https://chat.example/v1"
    assert config["embedding"]["api_key"] == "chat-key"
    assert config["embedding"]["model"] == "embed-model"


def test_langchain_provider_mock_stream_and_embedding() -> None:
    provider = LangChainLLMProvider()
    provider.settings.enable_mock_llm = True

    assert "".join(provider.chat_text_stream("system", "hello")) == "mock response"
    assert provider.embed_texts(["abc"]) == [[4.0, 0.1, 0.2, 0.3]]
    assert provider.chat_json("system", "hello", "RagAnswerOutput")["answer"]


def test_langchain_provider_sync_and_stream_with_fake_model() -> None:
    provider = LangChainLLMProvider()
    provider.settings.enable_mock_llm = False

    class FakeResponse:
        content = "hello"

    class FakeChunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeModel:
        def invoke(self, *_args, **_kwargs):
            return FakeResponse()

        def stream(self, *_args, **_kwargs):
            yield FakeChunk("hel")
            yield FakeChunk("lo")

    provider._chat_model = lambda _config: FakeModel()  # type: ignore[method-assign]
    config = {
        "chat": {
            "provider_type": "openai-compatible",
            "base_url": "https://chat.example/v1",
            "api_key": "chat-key",
            "model": "chat-model",
        }
    }

    assert provider.chat_text("system", "hello", model_config=config) == "hello"
    assert "".join(provider.chat_text_stream("system", "hello", model_config=config)) == "hello"


def test_langchain_embedding_disables_local_tokenizer_split(monkeypatch) -> None:
    provider = LangChainLLMProvider()
    provider.settings.enable_mock_llm = False
    captured_kwargs: dict[str, object] = {}

    class FakeEmbeddings:
        def __init__(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)

        def embed_documents(self, texts):
            return [[1.0, 2.0, 3.0] for _ in texts]

    monkeypatch.setattr(langchain_provider_module, "OpenAIEmbeddings", FakeEmbeddings)

    result = provider.embed_texts(
        ["connection check"],
        model_config={
            "embedding": {
                "provider_type": "openai-compatible",
                "base_url": "https://embed.example/v1",
                "api_key": "embed-key",
                "model": "embedding-3",
            }
        },
    )

    assert result == [[1.0, 2.0, 3.0]]
    assert captured_kwargs["model"] == "embedding-3"
    assert captured_kwargs["check_embedding_ctx_length"] is False


def test_dev_secret_fallback_encrypts_when_app_secret_keys_missing(monkeypatch) -> None:
    monkeypatch.delenv("APP_SECRET_KEYS", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    get_settings.cache_clear()
    secrets_module._fernet.cache_clear()
    try:
        encrypted = secrets_module.encrypt_secret("dev-secret")
        assert encrypted.startswith(secrets_module.SECRET_PREFIX)
        assert secrets_module.decrypt_secret(encrypted) == "dev-secret"
    finally:
        get_settings.cache_clear()
        secrets_module._fernet.cache_clear()


def test_model_provider_api_encrypts_and_masks_keys() -> None:
    client = TestClient(app)
    long_chat_secret = f"chat-{'x' * 280}-secret"

    response = client.post(
        "/api/v1/projects/demo-platform/models/providers",
        json={
            "name": "encrypted provider",
            "provider_type": "openai-compatible",
            "base_url": "https://chat.example/v1",
            "api_key": long_chat_secret,
            "default_chat_model": "chat-model",
            "default_embedding_model": "embed-model",
            "embedding_provider_type": "openai-compatible",
            "embedding_base_url": "https://embed.example/v1",
            "embedding_api_key": "embed-secret",
            "is_default": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert "api_key" not in payload
    assert payload["has_api_key"] is True
    assert payload["has_embedding_api_key"] is True
    assert payload["api_key_masked"] == "chat...cret"

    with SessionLocal() as db:
        provider = db.get(ModelProvider, payload["id"])
        assert provider.api_key.startswith("enc:v1:")
        assert len(provider.api_key) > 255
        assert long_chat_secret not in provider.api_key
        assert provider.embedding_api_key.startswith("enc:v1:")
        config = resolve_model_config(db, "demo-platform")

    assert config["chat"]["api_key"] == long_chat_secret
    assert config["embedding"]["api_key"] == "embed-secret"


def test_model_provider_secret_update_reencrypts_selected_keys() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/projects/demo-platform/models/providers",
        json={
            "name": "secret update provider",
            "provider_type": "openai-compatible",
            "base_url": "https://chat.example/v1",
            "api_key": "old-chat-secret",
            "default_chat_model": "chat-model",
            "default_embedding_model": "embed-model",
            "is_default": True,
        },
    )
    provider_id = create_response.json()["data"]["id"]

    response = client.patch(
        f"/api/v1/projects/demo-platform/models/providers/{provider_id}/secrets",
        json={"api_key": "new-chat-secret"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["has_api_key"] is True
    with SessionLocal() as db:
        provider = db.get(ModelProvider, provider_id)
        assert provider.api_key.startswith("enc:v1:")
        assert "new-chat-secret" not in provider.api_key
        config = resolve_model_config(db, "demo-platform")

    assert config["chat"]["api_key"] == "new-chat-secret"
    assert config["embedding"]["api_key"] == "new-chat-secret"


def test_model_provider_config_update_keeps_chat_and_embedding_separate() -> None:
    client = TestClient(app)
    create_response = client.post(
        "/api/v1/projects/demo-platform/models/providers",
        json={
            "name": "split save provider",
            "provider_type": "openai-compatible",
            "base_url": "https://chat.example/v1",
            "api_key": "chat-secret",
            "default_chat_model": "chat-model",
            "default_embedding_model": "old-embed-model",
            "is_default": True,
        },
    )
    provider_id = create_response.json()["data"]["id"]

    chat_response = client.patch(
        f"/api/v1/projects/demo-platform/models/providers/{provider_id}",
        json={
            "base_url": "https://new-chat.example/v1",
            "default_chat_model": "new-chat-model",
        },
    )
    embedding_response = client.patch(
        f"/api/v1/projects/demo-platform/models/providers/{provider_id}",
        json={
            "embedding_base_url": "https://embed.example/v1",
            "embedding_api_key": "embed-secret",
            "default_embedding_model": "new-embed-model",
        },
    )

    assert chat_response.status_code == 200
    assert embedding_response.status_code == 200
    payload = embedding_response.json()["data"]
    assert payload["base_url"] == "https://new-chat.example/v1"
    assert payload["default_chat_model"] == "new-chat-model"
    assert payload["embedding_base_url"] == "https://embed.example/v1"
    assert payload["default_embedding_model"] == "new-embed-model"
    assert payload["api_key_masked"] == "chat...cret"
    assert payload["embedding_api_key_masked"] == "embe...cret"

    with SessionLocal() as db:
        config = resolve_model_config(db, "demo-platform")

    assert config["chat"]["base_url"] == "https://new-chat.example/v1"
    assert config["chat"]["api_key"] == "chat-secret"
    assert config["embedding"]["base_url"] == "https://embed.example/v1"
    assert config["embedding"]["api_key"] == "embed-secret"
