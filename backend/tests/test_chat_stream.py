from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.routes import chat as chat_routes
from app.main import app
from app.services.llm.exceptions import LLMInvocationError


def _create_session(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects/demo-platform/chat/sessions",
        json={"title": "stream test", "user_id": "demo-user"},
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_stream_chat_message_emits_status_delta_done_and_persists_messages() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        json={"content": "介绍一下知识库状态", "action": "answer"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert body.index("event: status") < body.index("event: delta") < body.index("event: done")
    assert "mock response" in body

    messages_response = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["data"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == "mock response"


def test_stream_chat_message_error_does_not_persist_assistant_message(monkeypatch) -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    def fail_stream(*_args, **_kwargs):
        yield ("status", {"stage": "generate", "message": "starting"})
        raise LLMInvocationError("boom")

    monkeypatch.setattr(chat_routes, "stream_chat_graph", fail_stream)

    with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        json={"content": "会失败吗", "action": "answer"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: error" in body
    assert "boom" in body

    messages_response = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert messages_response.status_code == 200
    assert messages_response.json()["data"] == []
