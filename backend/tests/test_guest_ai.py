from fastapi.testclient import TestClient

from app.services.ai_provider import LLMProviderError


_ACTION = {
    "greenhouse_id": 101,
    "title": "检查通风设备",
    "description": "检查风机运行与通风口状态",
    "action_type": "ventilation_check",
    "priority": "medium",
    "due_at": None,
}


class FakeProvider:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    async def chat(self, messages, tools, tool_choice="auto"):
        self.calls.append((messages, tools, tool_choice))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_guest_chat_answers_without_creating_server_task(monkeypatch) -> None:
    provider = FakeProvider([{"role": "assistant", "content": "建议先检查风机和通风口。"}])
    monkeypatch.setattr("app.api.guest_ai.get_llm_provider", lambda: provider)

    response = TestClient(__import__("app.main", fromlist=["app"]).app).post(
        "/api/guest/ai/chat", json={"content": "通风设备应该检查什么？", "greenhouse_id": 101}
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "建议先检查风机和通风口。", "actions": []}
    assert len(provider.calls) == 1
    assert provider.calls[0][2] == "auto"


def test_guest_chat_retries_explicit_task_intent_and_limits_actions(monkeypatch) -> None:
    provider = FakeProvider([
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "已生成任务", "tool_calls": [
            {"function": {"name": "create_farm_task", "arguments": __import__("json").dumps(_ACTION, ensure_ascii=False)}},
            {"function": {"name": "create_farm_task", "arguments": __import__("json").dumps({**_ACTION, "title": "检查排风扇"}, ensure_ascii=False)}},
            {"function": {"name": "create_farm_task", "arguments": __import__("json").dumps({**_ACTION, "title": "第三项"}, ensure_ascii=False)}},
        ]},
    ])
    monkeypatch.setattr("app.api.guest_ai.get_llm_provider", lambda: provider)

    response = TestClient(__import__("app.main", fromlist=["app"]).app).post(
        "/api/guest/ai/chat", json={"content": "在番茄棚创建明天检查通风设备的任务", "greenhouse_id": 101}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["actions"]) == 2
    assert "检查通风设备" in data["reply"]
    assert len(provider.calls) == 2
    assert provider.calls[1][2] == {"type": "function", "function": {"name": "create_farm_task"}}


def test_guest_chat_rejects_invalid_greenhouse_and_action(monkeypatch) -> None:
    provider = FakeProvider([{"role": "assistant", "content": "没有创建任务。"}])
    monkeypatch.setattr("app.api.guest_ai.get_llm_provider", lambda: provider)
    app = __import__("app.main", fromlist=["app"]).app
    client = TestClient(app)

    invalid_greenhouse = client.post(
        "/api/guest/ai/chat", json={"content": "你好", "greenhouse_id": 999}
    )
    assert invalid_greenhouse.status_code == 422
    assert not provider.calls

    invalid_action = {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "create_farm_task", "arguments": "{}"}},
    ]}
    provider.results = [invalid_action]
    response = client.post(
        "/api/guest/ai/chat", json={"content": "创建一个检查任务", "greenhouse_id": 101}
    )
    assert response.status_code == 200
    assert response.json()["actions"] == []
    assert "已创建" not in response.json()["reply"]


def test_guest_chat_maps_provider_failure_to_service_unavailable(monkeypatch) -> None:
    provider = FakeProvider([LLMProviderError("模型服务不可用")])
    monkeypatch.setattr("app.api.guest_ai.get_llm_provider", lambda: provider)

    response = TestClient(__import__("app.main", fromlist=["app"]).app).post(
        "/api/guest/ai/chat", json={"content": "请介绍通风管理", "greenhouse_id": 101}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "模型服务不可用"

