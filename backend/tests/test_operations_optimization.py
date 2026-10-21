"""Regression coverage uses conftest's temporary database only."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import time

from app.database import SessionLocal
from app.models import FarmTask
from app.greenhouse_sim.runtime import Manager, Runtime
import app.greenhouse_sim.runtime as runtime_module
from test_task_api import task_context, create_manual  # noqa: F401


def test_task_server_search_pagination_schedule_and_summary(client, task_context):
    gid, bid = task_context
    ids = [create_manual(client, gid, bid)['id'] for _ in range(9)]
    start = datetime(2026, 10, 1, tzinfo=UTC)
    with SessionLocal() as db:
        for i, task_id in enumerate(ids):
            task = db.get(FarmTask, task_id)
            task.title = '巡查%_' if i == 0 else f'巡查{i}'
            task.status = ['draft', 'pending', 'in_progress', 'completed'][i % 4]
            task.planned_start_at = start + timedelta(days=8-i) if i < 8 else None
            task.due_at = start + timedelta(days=10)
        db.commit()
    filters = {'greenhouse_id': gid, 'sort': 'schedule', 'page_size': 6}
    first = client.get('/api/tasks', params=filters).json()['data']
    second = client.get('/api/tasks', params={**filters, 'page': 2}).json()['data']
    assert first['total'] == 9 and len(first['items']) == 6 and len(second['items']) == 3
    assert [t['id'] for t in first['items']+second['items']] == list(reversed(ids[:8])) + [ids[8]]
    pending = client.get('/api/tasks', params={**filters, 'status_group': 'pending'}).json()['data']
    assert pending['total'] == 5 and all(t['status'] in {'draft', 'pending'} for t in pending['items'])
    literal = client.get('/api/tasks', params={**filters, 'q': '%_'}).json()['data']
    assert literal['total'] == 1 and literal['items'][0]['id'] == ids[0]
    month = client.get('/api/tasks', params={**filters, 'scheduled_start': start.isoformat(), 'scheduled_end': (start+timedelta(days=5)).isoformat()}).json()['data']
    assert month['total'] == 4
    summary = client.get('/api/tasks/summary', params={'greenhouse_id': gid}).json()['data']
    assert summary['total'] == 9 and summary['completed_total'] == 2
    assert client.get('/api/tasks', params={'sort': 'invalid'}).status_code == 422


def test_task_new_filters_preserve_organization_scope(client, task_context):
    gid, bid = task_context
    create_manual(client, gid, bid)
    other = client.post('/api/auth/register', json={'display_name':'隔离账号','phone':'13900000009','organization':'另一组织','password':'Greenhouse2026'}).json()['data']['token']
    response = client.get('/api/tasks', params={'greenhouse_id':gid,'q':'检查','sort':'schedule'}, headers={'Authorization':f'Bearer {other}'})
    assert response.status_code == 200 and response.json()['data']['total'] == 0


def test_idle_mock_sessions_reclaimed_before_capacity_check(monkeypatch):
    monkeypatch.setattr(runtime_module, 'Runtime', lambda key, owner, device: Runtime(key, owner, device, persist=False))
    manager = Manager()
    for i in range(64):
        r = Runtime(f'demo:{i}', persist=False)
        r.last_seen = time.monotonic() - manager.IDLE_TTL - 1
        manager.runtimes[r.key] = r
    assert manager.get('demo:new').key == 'demo:new'
    assert list(manager.runtimes) == ['demo:new']


def test_reclamation_preserves_active_and_real_sessions():
    manager = Manager()
    active = Runtime('active', persist=False)
    active.running = True
    active.last_seen = time.monotonic() - manager.IDLE_TTL - 1
    real = Runtime('real', persist=False)
    real.link.device = SimpleNamespace(mode='real')
    real.last_seen = active.last_seen
    manager.real_owner = 'real'
    manager.runtimes = {'active': active, 'real': real}
    with manager.lock:
        manager._reap_idle()
    assert set(manager.runtimes) == {'active', 'real'} and manager.real_owner == 'real'


def test_input_baseline_survives_rolling_history(client):
    headers = {'X-Simulation-Session': 'baseline-regression'}
    response = client.put('/api/greenhouse-demo/state', json={'environment':{'air_humidity':85},'target':{'air_humidity':65}}, headers=headers)
    assert response.status_code == 200 and response.json()['humidity_baseline'] == 20
    runtime = runtime_module.manager.runtimes['demo:baseline-regression']
    runtime.history.extend({'time':i*2,'air_humidity':75} for i in range(1, 305))
    snapshot = runtime.snapshot()
    assert len(snapshot['history']) == 300 and snapshot['history'][0]['time'] > 0
    assert snapshot['humidity_baseline'] == 20
