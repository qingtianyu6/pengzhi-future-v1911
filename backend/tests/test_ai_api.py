from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import AIConversation, AIMessage, AIToolCall
from app.services.ai_provider import LLMProviderError


def _greenhouse(client: TestClient) -> int:
    response = client.post("/api/greenhouses", json={
        "code": "AI-GH-001",
        "name": "一号棚",
        "location": "AI助手测试区",
        "area_mu": 2,
        "status": "active",
    })
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_ai_conversation_crud_persists_in_database(client: TestClient) -> None:
    greenhouse_id = _greenhouse(client)
    created = client.post("/api/v1/ai/conversations", json={"greenhouse_id": greenhouse_id})
    assert created.status_code == 200
    conversation_id = created.json()["data"]["id"]

    renamed = client.patch(
        f"/api/v1/ai/conversations/{conversation_id}", json={"title": "一号棚风险分析"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["title"] == "一号棚风险分析"
    assert client.get("/api/v1/ai/conversations").json()["data"][0]["id"] == conversation_id

    with SessionLocal() as db:
        assert db.get(AIConversation, conversation_id) is not None

    deleted = client.delete(f"/api/v1/ai/conversations/{conversation_id}")
    assert deleted.status_code == 200
    with SessionLocal() as db:
        assert db.get(AIConversation, conversation_id) is None


def test_ai_status_uses_local_copilot_without_external_model(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(ai_api_key="", ai_base_url="", ai_model=""),
    )
    response = client.get("/api/v1/ai/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is True
    assert data["model"] == "pengzhi-local-agent"
    assert data["message"] == "本地农业智能体可用"
    assert data["knowledge_items"] >= 1


def test_ai_chat_stream_saves_messages_and_tool_evidence(
    client: TestClient, monkeypatch
) -> None:
    greenhouse_id = _greenhouse(client)
    conversation_id = client.post(
        "/api/v1/ai/conversations", json={"greenhouse_id": greenhouse_id}
    ).json()["data"]["id"]

    class FakeProvider:
        async def chat_stream(self, messages, tools):
            assert messages[0]["role"] == "system"
            assert len([item for item in messages if item["role"] in {"user", "assistant"}]) <= 10
            assert len(tools) == 5
            yield "当前数据不足；"
            yield "请人工确认现场情况。"

    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(ai_api_key="test", ai_base_url="http://example.test", ai_model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.ai_service.get_llm_provider", lambda: FakeProvider()
    )
    response = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/chat",
        json={"content": "分析当前风险"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in response.text
    assert "当前数据不足" in response.text

    messages = client.get(
        f"/api/v1/ai/conversations/{conversation_id}/messages"
    ).json()["data"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[-1]["status"] == "completed"
    assert "人工确认" in messages[-1]["content"]

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AIMessage)) == 2
        assert db.scalar(select(func.count()).select_from(AIToolCall)) == 4


def test_ai_local_copilot_can_answer_without_external_key(
    client: TestClient, monkeypatch
) -> None:
    greenhouse_id = _greenhouse(client)
    conversation_id = client.post(
        "/api/v1/ai/conversations", json={"greenhouse_id": greenhouse_id}
    ).json()["data"]["id"]
    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(ai_api_key="", ai_base_url="", ai_model=""),
    )
    response = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/chat",
        json={"content": "现在有什么风险"},
    )
    assert response.status_code == 200
    assert "event: delta" in response.text
    assert "暂无可用环境数据" in response.text


def test_ai_falls_back_to_local_knowledge_when_external_model_fails(
    client: TestClient, monkeypatch
) -> None:
    conversation_id = client.post(
        "/api/v1/ai/conversations", json={"title": "外部模型降级测试"}
    ).json()["data"]["id"]

    class FailingProvider:
        async def chat_stream(self, messages, tools):
            if False:
                yield ""
            raise LLMProviderError("upstream unavailable")

    monkeypatch.setattr(
        "app.services.ai_service.get_settings",
        lambda: SimpleNamespace(
            ai_api_key="test",
            ai_base_url="http://example.test",
            ai_model="fake-model",
        ),
    )
    monkeypatch.setattr(
        "app.services.ai_service.get_llm_provider", lambda: FailingProvider()
    )

    response = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/chat",
        json={"content": "番茄高湿时应该关注什么？"},
    )

    assert response.status_code == 200
    assert '"fallback": "local_knowledge"' in response.text
    assert "模型服务暂时不可用" not in response.text
    messages = client.get(
        f"/api/v1/ai/conversations/{conversation_id}/messages"
    ).json()["data"]
    assert messages[-1]["status"] == "completed"
    assert messages[-1]["content"]
