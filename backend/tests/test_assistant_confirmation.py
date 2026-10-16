from types import SimpleNamespace
from sqlalchemy import select
from app.database import SessionLocal
from app.models import AgentRun, FarmTask
from test_agent_runtime import calls, reply, conversation, install
from test_final_product import create_context


def prepare_interactive(client, monkeypatch, code):
    gh, _ = create_context(client, code)
    cid = conversation(client, gh)
    install(monkeypatch, [calls(('create_task_draft', {'greenhouse_id': gh,
        'title': '棚小智交互确认检查', 'description': '现场人员确认后检查通风', 'action_type': 'ventilation_check'})), reply()])
    monkeypatch.setattr('app.services.ai_service.get_settings', lambda: SimpleNamespace(
        ai_api_key='test-only', ai_base_url='http://test-only.invalid', ai_model='scripted-test'))
    monkeypatch.setattr('app.agent.guard.get_settings', lambda: SimpleNamespace(agent_software_approval=False))
    response = client.post(f'/api/v1/ai/conversations/{cid}/chat', json={
        'content': '整理通风检查任务草稿，等我确认', 'require_confirmation': True})
    assert response.status_code == 200, response.text
    assert 'approval_required' in response.text
    with SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.conversation_id == cid))
        assert run.status == 'WAITING_APPROVAL'
        assert run.context_json['require_confirmation'] is True
        assert db.scalar(select(FarmTask.id)) is None
        rid = run.id
    snapshot = client.get(f'/api/agent/runs/{rid}').json()['data']
    return rid, snapshot['approvals'][0]['id']


def test_interactive_chat_requires_confirmation_even_when_legacy_setting_is_off(client, monkeypatch):
    rid, approval = prepare_interactive(client, monkeypatch, 'ASSISTANT-CONFIRM')
    result = client.post(f'/api/agent/runs/{rid}/approve', json={'approval_id': approval})
    assert result.status_code == 200
    with SessionLocal() as db:
        tasks = list(db.scalars(select(FarmTask)))
        assert len(tasks) == 1 and tasks[0].status == 'draft'
    assert client.post(f'/api/agent/runs/{rid}/approve', json={'approval_id': approval}).status_code == 409
    with SessionLocal() as db:
        assert len(list(db.scalars(select(FarmTask)))) == 1


def test_interactive_reject_does_not_create_task(client, monkeypatch):
    rid, approval = prepare_interactive(client, monkeypatch, 'ASSISTANT-REJECT')
    result = client.post(f'/api/agent/runs/{rid}/reject', json={'approval_id': approval})
    assert result.status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(FarmTask.id)) is None


def reader(client):
    gh, _ = create_context(client, 'ASSISTANT-READER')
    result=client.post('/api/auth/members',json={'display_name':'只读测试员','phone':'13900007703','password':'Assistant2026','role':'observer'})
    assert result.status_code in (200,201),result.text
    login=client.post('/api/auth/login',json={'phone':'13900007703','password':'Assistant2026'}).json()['data']
    client.headers['Authorization']='Bearer '+login['token']
    return gh


def test_observer_can_ask_about_own_greenhouse_without_business_write_access(client,monkeypatch):
    gh=reader(client)
    monkeypatch.setattr('app.services.ai_service.get_settings',lambda:SimpleNamespace(ai_api_key='',ai_base_url='',ai_model=''))
    created=client.post('/api/v1/ai/conversations',json={'mode':'greenhouse','greenhouse_id':gh})
    assert created.status_code==200,created.text
    cid=created.json()['data']['id']
    response=client.post(f'/api/v1/ai/conversations/{cid}/chat',json={'content':'本棚当前情况如何','require_confirmation':True})
    assert response.status_code==200 and 'event: done' in response.text,response.text
    assert client.post('/api/tasks',json={'greenhouse_id':gh,'title':'不应创建','description':'检查','action_type':'field_inspection','created_by':'只读测试员'}).status_code==403


def test_observer_model_tool_cannot_turn_query_access_into_task_write(client,monkeypatch):
    gh=reader(client)
    cid=client.post('/api/v1/ai/conversations',json={'mode':'greenhouse','greenhouse_id':gh}).json()['data']['id']
    install(monkeypatch,[calls(('create_task_draft',{'greenhouse_id':gh,'title':'不应执行','description':'只读角色不能创建','action_type':'field_inspection'})),reply()])
    response=client.post('/api/agent/chat',json={'conversation_id':cid,'content':'查看本棚情况'})
    assert response.status_code==200,response.text
    with SessionLocal() as db:
        assert db.scalar(select(FarmTask.id)) is None
