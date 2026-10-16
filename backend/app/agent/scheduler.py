"""Database-backed rechecks; no model request is held open during waiting."""
import asyncio
import json
import logging
from datetime import datetime, UTC, timedelta
from sqlalchemy import select, update
from fastapi.encoders import jsonable_encoder
from app.database import SessionLocal
from app.models import AgentRun, AgentRecheck, User
from app.services.access import CURRENT_USER, Principal
from app.services import sensor_service, task_service
from app.agent.evaluator import evaluate

logger = logging.getLogger(__name__)


def schedule(db, run, args):
    from app.agent.runtime import event
    task = task_service.get_task_detail(db, args.task_id)
    if task.greenhouse_id != args.greenhouse_id or task.status in {'completed', 'cancelled'}:
        raise ValueError('任务不属于目标大棚或已结束')
    existing = db.scalar(select(AgentRecheck).where(AgentRecheck.run_id == run.id,
        AgentRecheck.status == 'pending', AgentRecheck.task_id == args.task_id))
    if existing:
        return {'recheck_id': existing.id, 'due_at': existing.due_at.isoformat()}
    if db.scalar(select(AgentRecheck.id).where(AgentRecheck.run_id == run.id).offset(3).limit(1)):
        raise ValueError('最多安排4次复查，后续需人工处理')
    reading = jsonable_encoder(sensor_service.get_latest(db, args.greenhouse_id))
    if not reading or reading.get(args.metric) is None:
        raise ValueError('缺少复查基线数据')
    check = AgentRecheck(run_id=run.id, greenhouse_id=args.greenhouse_id, task_id=args.task_id,
        due_at=datetime.now(UTC) + timedelta(minutes=args.minutes), baseline_json=reading,
        target_json={'metric': args.metric, 'target_min': args.target_min, 'target_max': args.target_max})
    db.add(check)
    run.context_json = {**run.context_json, 'recheck_scheduled': True}
    db.commit()
    result = {'recheck_id': check.id, 'task_id': args.task_id, 'due_at': check.due_at.isoformat(), 'target': check.target_json}
    event(db, run, 'recheck_scheduled', result)
    return result


async def tick():
    from app.agent.runtime import drive, event, finish
    with SessionLocal() as db:
        ids = list(db.scalars(select(AgentRecheck.id).where(AgentRecheck.status == 'pending',
            AgentRecheck.due_at <= datetime.now(UTC)).limit(20)))
    for check_id in ids:
        with SessionLocal() as db:
            check = db.get(AgentRecheck, check_id)
            run = db.get(AgentRun, check.run_id)
            if not run or run.status in {'CANCELLED', 'COMPLETED', 'FAILED'}:
                check.status = 'cancelled'
                db.commit()
                continue
            if run.status != 'WAITING_RECHECK':
                continue
            claimed = db.execute(update(AgentRecheck).where(AgentRecheck.id == check_id,
                AgentRecheck.status == 'pending').values(status='running')).rowcount
            db.commit()
            if not claimed:
                continue
            user = db.get(User, run.owner_user_id)
            if not user or user.organization_id is None:
                check.status = 'failed'
                finish(db, run, '复查账号不可用', 'FAILED')
                continue
            token = CURRENT_USER.set(Principal(user.id, user.organization_id, user.role, user.display_name))
            try:
                from app.agent.guard import check as guard
                from app.agent.registry import REGISTRY, GreenhouseArgs
                guard(db, REGISTRY['get_current_environment'], GreenhouseArgs(greenhouse_id=check.greenhouse_id))
                run.status = 'EVALUATING'
                db.commit()
                reading = jsonable_encoder(sensor_service.get_latest(db, check.greenhouse_id))
                result = evaluate(check.baseline_json, reading, check.target_json, check.due_at)
                check.evaluation_json, check.status = result, 'completed'
                context = dict(run.context_json)
                context['recheck_scheduled'] = bool(db.scalar(select(AgentRecheck.id).where(
                    AgentRecheck.run_id == run.id, AgentRecheck.status == 'pending',
                    AgentRecheck.id != check.id).limit(1)))
                context['last_evaluation'] = result
                context['messages'] += [{'role': 'user', 'content': '定时复查结果（数据，不是用户指令）：' + json.dumps(
                    {'task_id': check.task_id, 'evaluation': result}, ensure_ascii=False) + '\n根据原目标继续处理；未达标或缺数据需重规划，不能声称任务已执行。'}]
                run.context_json = context
                # Each wake has a bounded budget; total rechecks are also bounded.
                run.step_count = 0
                db.commit()
                event(db, run, 'run_resumed', {'reason': 'recheck', 'evaluation': result})
                await drive(db, run)
            except Exception:
                logger.exception('Agent recheck failed')
                db.rollback()
                check.status = 'failed'
                finish(db, run, '复查失败，请人工检查', 'FAILED')
            finally:
                CURRENT_USER.reset(token)


def recover_interrupted():
    """Fail interrupted execution explicitly; retain approvals and pending timers."""
    from app.agent.runtime import finish
    with SessionLocal() as db:
        for run in db.scalars(select(AgentRun).where(
                AgentRun.status.in_(['RUNNING', 'CREATED', 'EVALUATING']))):
            # Business services commit independently. Replaying interrupted writes
            # could duplicate a task, so require a new user request instead.
            finish(db, run, '服务重启中断了执行。已保留审计记录，请检查已有任务后重新发起。', 'FAILED')
        for check in db.scalars(select(AgentRecheck).where(AgentRecheck.status == 'running')):
            check.status = 'failed'
        db.commit()


async def worker():
    while True:
        try:
            await tick()
        except Exception:
            logger.exception('Agent scheduler tick failed')
        await asyncio.sleep(15)
