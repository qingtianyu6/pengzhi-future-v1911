from sqlalchemy import select
from app.models import AgentRecheck, Intervention
from app.services import task_service, case_service


def save_case(db, run, task_id):
    task = task_service.get_task_detail(db, task_id)
    check = db.scalar(select(AgentRecheck).where(AgentRecheck.run_id == run.id,
        AgentRecheck.task_id == task_id, AgentRecheck.status == 'completed').order_by(AgentRecheck.id.desc()))
    if task.status != 'completed' or not check or not check.evaluation_json.get('achieved'):
        raise ValueError('只有已完成任务和达标复查可以保存案例')
    intervention = db.scalar(select(Intervention).where(Intervention.task_id == task_id))
    if intervention:
        return {'case': case_service.get_case(db, intervention.id).model_dump(mode='json'), 'storage': 'existing_case_service'}
    # Manual tasks have no Intervention. Keep the compact case in their existing
    # persisted evidence, rather than inventing a warning/candidate association.
    case = {'situation': check.baseline_json, 'decision': run.goal,
            'action': {'task_id': task.id, 'title': task.title}, 'outcome': check.evaluation_json}
    from app.models import FarmTask
    row = db.get(FarmTask, task_id)
    row.result_snapshot_json = {**(row.result_snapshot_json or {}), 'agent_case': case}
    db.commit()
    return {'task_id': task_id, 'storage': 'task_result_snapshot', 'case': case}
