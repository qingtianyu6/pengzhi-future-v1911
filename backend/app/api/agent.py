import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import AgentRun, AgentStep, AgentApproval, AgentRecheck, AgentToolCall
from app.schemas.ai import AIChatRequest
from app.schemas.common import ApiResponse
from app.services import ai_service
from app.agent import runtime

router = APIRouter(prefix='/agent', tags=['棚小智Agent'])
Database = Annotated[Session, Depends(get_db)]


class ChatRequest(BaseModel):
    conversation_id: int = Field(gt=0)
    content: str = Field(min_length=1, max_length=4000)


class ApprovalRequest(BaseModel):
    approval_id: int = Field(gt=0)


def snapshot(db, run):
    return {'id': run.id, 'conversation_id': run.conversation_id, 'message_id': run.message_id,
            'status': run.status, 'goal': run.goal, 'result': run.result,
            'step_count': run.step_count,
            'approvals': [{'id': a.id, 'status': a.status, 'tool': c.name,
                           'arguments': c.arguments_json, 'risk': c.risk}
                for a, c in db.execute(select(AgentApproval, AgentToolCall).join(
                    AgentToolCall, AgentToolCall.id == AgentApproval.tool_call_id).where(AgentApproval.run_id == run.id))],
            'rechecks': [{'id': c.id, 'status': c.status, 'due_at': c.due_at,
                         'task_id': c.task_id, 'target': c.target_json,
                         'evaluation': c.evaluation_json} for c in db.scalars(
                             select(AgentRecheck).where(AgentRecheck.run_id == run.id))]}


@router.post('/chat')
async def chat(payload: ChatRequest, db: Database):
    conversation, user, assistant = ai_service.prepare_chat(db, payload.conversation_id,
        AIChatRequest(content=payload.content))
    run = runtime.start(db, conversation, user, assistant)
    await runtime.drive(db, run)
    return ApiResponse(data=snapshot(db, run))


@router.get('/runs')
def list_runs(conversation_id: int, db: Database):
    from app.models import AgentRun
    from app.services.access import actor
    rows = db.scalars(select(AgentRun).where(AgentRun.owner_user_id == actor().id,
        AgentRun.conversation_id == conversation_id).order_by(AgentRun.id.desc()).limit(10))
    return ApiResponse(data=[snapshot(db, run) for run in rows])


@router.get('/runs/{run_id}')
def get_run(run_id: int, db: Database):
    return ApiResponse(data=snapshot(db, runtime.load(db, run_id)))


@router.get('/runs/{run_id}/events')
async def events(run_id: int, request: Request, db: Database, after: int = 0):
    runtime.load(db, run_id)
    async def stream():
        cursor = max(0, after)
        while not await request.is_disconnected():
            with SessionLocal() as session:
                run = session.get(AgentRun, run_id)
                if run is None:
                    break
                rows = list(session.scalars(select(AgentStep).where(AgentStep.run_id == run_id,
                    AgentStep.id > cursor).order_by(AgentStep.id).limit(100)))
                status = run.status
                for row in rows:
                    cursor = row.id
                    yield f'id: {row.id}\nevent: {row.event}\ndata: {json.dumps(row.data_json, ensure_ascii=False, default=str)}\n\n'
                if status in {'COMPLETED', 'FAILED', 'CANCELLED', 'WAITING_APPROVAL', 'WAITING_RECHECK'} and len(rows) < 100:
                    break
            if not rows:
                yield ': heartbeat\n\n'
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.post('/runs/{run_id}/approve')
async def approve(run_id: int, payload: ApprovalRequest, db: Database):
    run = runtime.load(db, run_id)
    runtime.decide(db, run, payload.approval_id, True)
    await runtime.drive(db, run)
    return ApiResponse(data=snapshot(db, run))


@router.post('/runs/{run_id}/reject')
async def reject(run_id: int, payload: ApprovalRequest, db: Database):
    run = runtime.load(db, run_id)
    runtime.decide(db, run, payload.approval_id, False)
    await runtime.drive(db, run)
    return ApiResponse(data=snapshot(db, run))


@router.post('/runs/{run_id}/cancel')
def cancel(run_id: int, db: Database):
    run = runtime.load(db, run_id)
    from app.agent.runtime import finish
    if run.status not in {'COMPLETED', 'FAILED', 'CANCELLED'}:
        run.context_json = {**run.context_json, 'pending': []}
        for check in db.scalars(select(AgentRecheck).where(AgentRecheck.run_id == run.id, AgentRecheck.status == 'pending')):
            check.status = 'cancelled'
        finish(db, run, '用户已取消运行。', 'CANCELLED')
    return ApiResponse(data=snapshot(db, run))
