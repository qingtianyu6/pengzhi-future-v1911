from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import FarmTask
from app.models.agronomist import AgronomyRecord, CropObservation
from test_final_product import create_context, readings


def post(client, path, payload, status=201):
    response = client.post('/api/agronomist/' + path, json=payload)
    assert response.status_code == status, response.text
    return response.json()['data']


def action(client, item, name, status=200):
    return post(client, f"records/{item['id']}/actions", {'version': item['version'], 'action': name}, status)


def test_archive_comparison_and_full_research_cycle(client):
    gid, bid = create_context(client, 'AGRONOMY')
    ctx = {'greenhouse_id': gid, 'crop_batch_id': bid}
    empty = client.get('/api/agronomist/archive', params=ctx).json()['data']
    assert empty['latest'] is None and empty['gaps'] and empty['batch']['id'] == bid
    assert client.post('/api/sensors/batch', json={'items': readings(gid, 'import')}).status_code == 200
    scenario = post(client, 'scenarios', {**ctx, 'duration_minutes': 60, 'intensity': 30})
    candidates = scenario['payload']['candidates']
    assert len(candidates) == 3
    assert candidates[0]['end']['humidity'] == scenario['payload']['baseline']['humidity']
    assert candidates[1]['end']['humidity'] < candidates[0]['end']['humidity']
    assert candidates[2]['end']['humidity'] < candidates[1]['end']['humidity']
    study = post(client, 'studies', {**ctx, 'question': '清晨叶面湿润与通风时间有什么关系？', 'scenario_id': scenario['id']})
    assert study['payload']['scenario_snapshot']['id'] == scenario['id']
    study = action(client, study, 'start')
    assert client.post(f"/api/agronomist/records/{study['id']}/actions", json={'version': study['version'], 'action': 'complete'}).status_code == 422
    now = datetime.now(UTC)
    for phase, minutes, value in [('before', -60, 70), ('after', 0, 35)]:
        post(client, 'observations', {**ctx, 'study_id': study['id'], 'phase': phase,
            'zone': '东侧', 'note': f'{phase} 叶面观察', 'metrics': {'leaf_wetness_pct': value},
            'observed_at': (now+timedelta(minutes=minutes)).isoformat()})
    study = action(client, study, 'complete')
    result = study['payload']['conclusion']
    assert study['status'] == 'completed' and result['comparisons'][0]['delta'] == -35
    skill = action(client, study, 'derive_skill')
    assert skill['status'] == 'draft' and skill['payload']['source_snapshot']['status'] == 'completed'
    assert action(client, study, 'derive_skill')['id'] == skill['id']
    skill = action(client, skill, 'activate')
    goal = post(client, 'goals', {**ctx, 'goal': '改善清晨湿度并完成复查', 'scenario_id': scenario['id'], 'skill_id': skill['id'], 'study_id': study['id']})
    assert goal['payload']['links']['skill']['version'] == skill['version']
    skill = action(client, skill, 'disable')
    unchanged = client.get('/api/agronomist/records', params=ctx).json()['data']
    stored_goal = next(r for r in unchanged['records'] if r['id'] == goal['id'])
    assert stored_goal['payload']['links']['skill']['status'] == 'active'
    goal = action(client, goal, 'execute')
    assert len(goal['payload']['task_ids']) == 4 and goal['status'] == 'running'
    assert client.post(f"/api/agronomist/records/{goal['id']}/actions", json={'version': 1, 'action': 'execute'}).status_code == 409
    task_ids = goal['payload']['task_ids']
    with SessionLocal() as db:
        tasks = list(db.scalars(select(FarmTask).where(FarmTask.id.in_(task_ids)).order_by(FarmTask.id)))
        assert len(tasks) == 4
        assert tasks[1].evidence_snapshot_json['agronomist_goal']['depends_on_task_ids'] == [tasks[0].id]
    # The existing task lifecycle enforces goal step ordering and exposes progress.
    submit = client.post(f'/api/tasks/{task_ids[1]}/submit', json={'version': 1, 'operator': '测试员'})
    assert submit.status_code == 200, submit.text
    blocked = client.post(f'/api/tasks/{task_ids[1]}/start', json={'version': 2, 'operator': '测试员'})
    assert blocked.status_code == 409
    archive = client.get('/api/agronomist/archive', params=ctx).json()['data']
    assert len(archive['observations']) == 2 and archive['sample_count'] == 24
    assert any(e['type'] == 'observation' for e in archive['timeline'])
    assert client.post(f"/api/agronomist/records/{goal['id']}/actions", json={'version': goal['version'], 'action': 'complete'}).status_code == 422
    for task_id in task_ids:
        task = client.get(f'/api/tasks/{task_id}').json()['data']
        if task['status'] == 'draft':
            response = client.post(f'/api/tasks/{task_id}/submit', json={'version': task['version'], 'operator': '测试员'})
            assert response.status_code == 200, response.text
            task = response.json()['data']
        response = client.post(f'/api/tasks/{task_id}/start', json={'version': task['version'], 'operator': '测试员'})
        assert response.status_code == 200, response.text
        task = response.json()['data']
        response = client.post(f'/api/tasks/{task_id}/complete', json={
            'version': task['version'], 'operator': '测试员', 'executed_at': now.isoformat(),
            'result_type': 'improved', 'execution_note': '已检查并记录观察结果'})
        assert response.status_code == 200, response.text
    goal = action(client, goal, 'complete')
    assert goal['status'] == 'completed'


def test_context_links_and_delete_cleanup(client):
    gid, bid = create_context(client, 'AGRONOMY-A')
    gid2, bid2 = create_context(client, 'AGRONOMY-B')
    study = post(client, 'studies', {'greenhouse_id': gid, 'question': '观察坐果差异'})
    mismatch = client.post('/api/agronomist/goals', json={'greenhouse_id': gid2, 'study_id': study['id'], 'goal': '观察坐果情况'})
    assert mismatch.status_code == 422
    assert client.get('/api/agronomist/archive', params={'greenhouse_id': gid, 'crop_batch_id': bid2}).status_code == 404
    post(client, 'observations', {'greenhouse_id': gid, 'note': '常规生长观察'})
    assert client.delete(f'/api/greenhouses/{gid}').status_code in (200, 204)
    with SessionLocal() as db:
        assert db.scalar(select(AgronomyRecord).where(AgronomyRecord.crop_batch_id == bid)) is None
        assert db.scalar(select(CropObservation).where(CropObservation.crop_batch_id == bid)) is None


def test_research_requires_ordered_comparable_measurements(client):
    gid, _ = create_context(client, 'AGRONOMY-TIME')
    study = action(client, post(client, 'studies', {'greenhouse_id': gid, 'question': '比较果实数变化'}), 'start')
    now = datetime.now(UTC)
    for phase in ('before', 'after'):
        post(client, 'observations', {'greenhouse_id': gid, 'study_id': study['id'], 'phase': phase,
             'note': '观察记录', 'metrics': {'fruit_count': 5}, 'observed_at': now.isoformat()})
    response = client.post(f"/api/agronomist/records/{study['id']}/actions", json={'version': study['version'], 'action': 'complete'})
    assert response.status_code == 422
    for metrics in ({'leaf_wetness_pct': 110}, {'fruit_count': -1}):
        response = client.post('/api/agronomist/observations', json={'greenhouse_id': gid, 'note': '异常指标', 'metrics': metrics})
        assert response.status_code == 422


def test_new_account_does_not_see_other_archives(client):
    gid, _ = create_context(client, 'AGRONOMY-OWNER')
    study = post(client, 'studies', {'greenhouse_id': gid, 'question': '研究问题'})
    registration = client.post('/api/auth/register', json={'display_name': '第二个组织', 'phone': '13900000001', 'organization': '独立组织', 'password': 'Greenhouse2026'})
    client.headers['Authorization'] = f"Bearer {registration.json()['data']['token']}"
    assert client.get('/api/agronomist/archive', params={'greenhouse_id': gid}).status_code == 404
    assert client.post(f"/api/agronomist/records/{study['id']}/actions", json={'version': 1, 'action': 'start'}).status_code == 404


def test_model_generated_plan_and_invalid_dependencies(client, monkeypatch):
    import json
    from app.services import ai_provider
    gid, _ = create_context(client, 'AGRONOMY-MODEL')
    class Provider:
        async def chat(self, messages, tools):
            assert '果实数' in messages[-1]['content']
            return {'content': json.dumps({'steps': [
                {'title': '按区域核对果实数', 'description': '选择固定植株记录果实数量', 'action_type': 'manual_observation', 'depends_on': []},
                {'title': '追踪坐果差异', 'description': '同一区域再次记录并整理变化', 'action_type': 'field_inspection', 'depends_on': [0]},
            ]}, ensure_ascii=False)}
    monkeypatch.setattr(ai_provider, 'get_llm_provider', lambda: Provider())
    goal = post(client, 'goals', {'greenhouse_id': gid, 'goal': '检查果实数差异', 'use_ai': True})
    assert goal['payload']['planner'] == '模型定制目标编排'
    assert len(goal['payload']['steps']) == 2
    malformed = client.post('/api/agronomist/goals', json={'greenhouse_id': gid, 'goal': '无效依赖', 'plan_steps': [
        {'title': '步骤一', 'description': '记录', 'action_type': 'manual_observation', 'depends_on': [1]},
        {'title': '步骤二', 'description': '检查', 'action_type': 'field_inspection', 'depends_on': [0]}]})
    assert malformed.status_code == 422
