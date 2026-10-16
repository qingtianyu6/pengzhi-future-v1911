import json
from itertools import count

_CALL_IDS = count()
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import AgentRun, AgentToolCall, AgentRecheck, FarmTask
from test_final_product import create_context, readings


class ScriptedProvider:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.messages = []

    async def chat(self, messages, tools):
        self.messages.append(messages)
        return next(self.batches)


def calls(*items):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': f'call-{next(_CALL_IDS)}-{name}', 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(args)}} for i, (name, args) in enumerate(items)]}


def reply():
    return {'role': 'assistant', 'content': '已根据真实工具结果处理。'}


def conversation(client, greenhouse_id):
    return client.post('/api/v1/ai/conversations', json={
        'mode': 'greenhouse', 'greenhouse_id': greenhouse_id}).json()['data']['id']


def run_chat(client, cid, content='检查大棚'):
    response = client.post('/api/agent/chat', json={'conversation_id': cid, 'content': content})
    assert response.status_code == 200, response.text
    return response.json()['data']


def install(monkeypatch, batches):
    provider = ScriptedProvider(batches)
    monkeypatch.setattr('app.agent.runtime.get_llm_provider', lambda: provider)
    return provider


def test_read_tools_and_audit(client, monkeypatch):
    gh, _ = create_context(client, 'AGENT-READ')
    install(monkeypatch, [calls(*[(name, {'greenhouse_id': gh}) for name in (
        'get_current_environment', 'get_future_prediction', 'get_active_warnings', 'get_risk_summary')]), reply()])
    run = run_chat(client, conversation(client, gh))
    assert run['status'] == 'COMPLETED'
    with SessionLocal() as db:
        audit = list(db.scalars(select(AgentToolCall).where(AgentToolCall.run_id == run['id'])))
        assert len(audit) == 4
        assert all(a.status == 'completed' for a in audit)
    events = client.get(f"/api/agent/runs/{run['id']}/events")
    assert 'tool_finished' in events.text


def test_invalid_arguments_and_exception_are_observations(client, monkeypatch):
    gh, _ = create_context(client, 'AGENT-INVALID')
    provider = install(monkeypatch, [calls(('get_current_environment', {'greenhouse_id': -1}),
        ('unknown_tool', {})), reply()])
    run = run_chat(client, conversation(client, gh))
    assert run['status'] == 'COMPLETED'
    assert sum(m['role'] == 'tool' and 'error' in m['content'] for m in provider.messages[-1]) == 2


def test_bounded_loop(client, monkeypatch):
    gh, _ = create_context(client, 'AGENT-LIMIT')
    batches = [calls(('get_current_environment', {'greenhouse_id': gh})) for _ in range(20)]
    install(monkeypatch, batches)
    run = run_chat(client, conversation(client, gh))
    assert run['status'] == 'FAILED'
    assert run['step_count'] == 8


def test_approval_resumes_same_run(client, monkeypatch):
    gh, _ = create_context(client, 'AGENT-APPROVE')
    monkeypatch.setattr('app.agent.guard.get_settings', lambda: SimpleNamespace(agent_software_approval=True))
    install(monkeypatch, [calls(('create_farm_task', {'greenhouse_id': gh,
        'title': '通风检查', 'description': '人员检查通风状况', 'action_type': 'ventilation_check'})), reply()])
    run = run_chat(client, conversation(client, gh))
    assert run['status'] == 'WAITING_APPROVAL'
    with SessionLocal() as db:
        assert not db.scalar(select(FarmTask.id))
    response = client.post(f"/api/agent/runs/{run['id']}/approve", json={'approval_id': run['approvals'][0]['id']})
    assert response.status_code == 200, response.text
    assert response.json()['data']['id'] == run['id']
    assert response.json()['data']['status'] == 'COMPLETED'
    with SessionLocal() as db:
        assert db.scalar(select(FarmTask)).status == 'pending'


def test_recheck_resumes_same_run(client, monkeypatch):
    gh, _ = create_context(client, 'AGENT-RECHECK')
    assert client.post('/api/sensors/batch', json={'items': readings(gh, 'sensor', 1)}).status_code == 200
    task = client.post('/api/tasks', json={'greenhouse_id': gh, 'title': '检查',
        'description': '检查环境', 'action_type': 'ventilation_check', 'created_by': '测试员'}).json()['data']
    install(monkeypatch, [calls(('schedule_recheck', {'greenhouse_id': gh, 'task_id': task['id'],
        'minutes': 30, 'target_min': 20.0, 'target_max': 28.0})), reply(), reply()])
    run = run_chat(client, conversation(client, gh))
    assert run['status'] == 'WAITING_RECHECK'
    with SessionLocal() as db:
        check = db.scalar(select(AgentRecheck))
        check.due_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    data = readings(gh, 'sensor', 1)[0]
    data['recorded_at'] = datetime.now(UTC).isoformat()
    assert client.post('/api/sensors/batch', json={'items': [data]}).status_code == 200
    import asyncio
    from app.agent.scheduler import tick
    asyncio.run(tick())
    with SessionLocal() as db:
        assert db.get(AgentRun, run['id']).status == 'COMPLETED'
        assert db.scalar(select(AgentRecheck)).evaluation_json['achieved'] is True


def test_cross_greenhouse_and_tomorrow_plan(client, monkeypatch):
    first, _ = create_context(client, 'AGENT-B')
    second, _ = create_context(client, 'AGENT-D')
    provider = install(monkeypatch, [calls(('list_greenhouses', {})),
        calls(('get_risk_summary', {'greenhouse_id': first}),
              ('get_risk_summary', {'greenhouse_id': second})), reply(),
        calls(*[(name, {'greenhouse_id': first}) for name in
              ('get_future_prediction', 'get_active_warnings', 'get_farm_tasks')]), reply()])
    cid = conversation(client, first)
    assert run_chat(client, cid, '今天哪个棚需要关注？')['status'] == 'COMPLETED'
    assert run_chat(client, cid, '安排明天的农事工作')['status'] == 'COMPLETED'
    assert all('error' not in m['content'] for m in provider.messages[-1] if m['role'] == 'tool')


def test_handling_closes_task_and_saves_searchable_case(client, monkeypatch):
    gh, _ = create_context(client, 'AGENT-C')
    assert client.post('/api/sensors/batch', json={'items': readings(gh, 'sensor', 1)}).status_code == 200
    task_args = {'greenhouse_id': gh, 'title': '降温通风检查',
                 'description': '人员确认环境并检查通风', 'action_type': 'ventilation_check'}
    install(monkeypatch, [calls(*[(name, {'greenhouse_id': gh}) for name in
        ('get_current_environment', 'get_future_prediction', 'get_active_warnings', 'search_similar_cases')]),
        calls(('create_farm_task', task_args)),
        calls(('schedule_recheck', {'greenhouse_id': gh, 'task_id': 1, 'minutes': 30,
                                   'target_min': 20.0, 'target_max': 28.0})), reply(),
        calls(('close_farm_task', {'task_id': 1, 'version': 3})),
        calls(('save_case_memory', {'task_id': 1, 'version': 4})), reply()])
    run = run_chat(client, conversation(client, gh), '大棚太热了，请处理并复查')
    assert run['status'] == 'WAITING_RECHECK'
    assert client.post('/api/tasks/1/start', json={'version': 2, 'operator': '现场人员'}).status_code == 200
    with SessionLocal() as db:
        check = db.scalar(select(AgentRecheck))
        check.due_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    data = readings(gh, 'sensor', 1)[0]
    data['recorded_at'] = datetime.now(UTC).isoformat()
    assert client.post('/api/sensors/batch', json={'items': [data]}).status_code == 200
    import asyncio
    from app.agent.scheduler import tick
    asyncio.run(tick())
    with SessionLocal() as db:
        assert db.get(AgentRun, run['id']).status == 'COMPLETED'
        task = db.get(FarmTask, 1)
        assert task.status == 'completed'
        assert task.result_snapshot_json['agent_case']['outcome']['achieved']
        from app.services.case_service import list_task_case_memories
        assert list_task_case_memories(db, gh)[0]['task_id'] == 1


def test_image_record_unavailable_model_is_reported(client, monkeypatch, tmp_path):
    from test_disease_api import FakePredictor, image_bytes
    gh, batch = create_context(client, 'AGENT-E')
    monkeypatch.setattr('app.services.disease_service.UPLOAD_DIR', tmp_path)
    monkeypatch.setattr('app.services.disease_service.get_disease_predictor', lambda: FakePredictor('model_unavailable'))
    response = client.post('/api/diseases/identify', data={'greenhouse_id': gh, 'crop_batch_id': batch},
        files={'image': ('leaf.jpg', image_bytes(), 'image/jpeg')})
    assert response.status_code == 200
    record_id = response.json()['data']['record_id']
    provider = install(monkeypatch, [calls(('diagnose_crop_image', {'record_id': record_id}),
        ('get_current_environment', {'greenhouse_id': gh}),
        ('search_agriculture_knowledge', {'query': '叶片现场复核'})), reply()])
    assert run_chat(client, conversation(client, gh), f'叶片识别记录{record_id}怎么处理？')['status'] == 'COMPLETED'
    assert any('model_unavailable' in m['content'] for m in provider.messages[-1] if m['role'] == 'tool')


def test_stale_recheck_cannot_claim_success():
    from app.agent.evaluator import evaluate
    due = datetime.now(UTC)
    result = evaluate({'temperature': 35}, {'temperature': 25, 'quality_flag': 'valid',
        'recorded_at': (due - timedelta(hours=1)).isoformat()},
        {'metric': 'temperature', 'target_min': 20, 'target_max': 28}, due)
    assert result['achieved'] is False
    assert result['data_status'] == 'insufficient_data'


def test_physical_tool_requires_approval(client, monkeypatch):
    from app.agent.registry import REGISTRY, Tool, GreenhouseArgs
    gh, _ = create_context(client, 'AGENT-PHYSICAL')
    executed = []
    monkeypatch.setitem(REGISTRY, 'test_device', Tool('test_device', 'test', GreenhouseArgs,
        'PHYSICAL_ACTION', lambda *args: executed.append(True) or {'ok': True}))
    install(monkeypatch, [calls(('test_device', {'greenhouse_id': gh})), reply()])
    run = run_chat(client, conversation(client, gh))
    assert run['status'] == 'WAITING_APPROVAL'
    assert not executed
    response = client.post(f"/api/agent/runs/{run['id']}/reject", json={'approval_id': run['approvals'][0]['id']})
    assert response.status_code == 200
    assert not executed
