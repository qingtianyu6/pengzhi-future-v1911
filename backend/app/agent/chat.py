import asyncio
from sqlalchemy import select
from app.database import SessionLocal
from app.models import AgentStep, AIMessage
from app.schemas.ai import AIMessageData
from app.agent import runtime


async def stream_agent_chat(db, conversation, user, assistant, *, require_confirmation=False):
    yield {'event': 'meta', 'data': {
        'conversation_id': conversation.id,
        'user_message': AIMessageData.model_validate(user).model_dump(mode='json'),
        'assistant_message': AIMessageData.model_validate(assistant).model_dump(mode='json')}}
    run = runtime.start(db, conversation, user, assistant, require_confirmation=require_confirmation)
    run_id = run.id

    async def execute():
        with SessionLocal() as worker_db:
            await runtime.drive(worker_db, runtime.load(worker_db, run_id))

    task = asyncio.create_task(execute())
    cursor = 0
    try:
        while True:
            db.rollback()
            rows = list(db.scalars(select(AgentStep).where(AgentStep.run_id == run_id,
                AgentStep.id > cursor).order_by(AgentStep.id)))
            for row in rows:
                cursor = row.id
                yield {'event': row.event, 'data': {**row.data_json, 'run_id': run_id}}
            if task.done():
                await task
                db.rollback()
                remaining = list(db.scalars(select(AgentStep).where(AgentStep.run_id == run_id,
                    AgentStep.id > cursor).order_by(AgentStep.id)))
                for row in remaining:
                    cursor = row.id
                    yield {'event': row.event, 'data': {**row.data_json, 'run_id': run_id}}
                assistant = db.get(AIMessage, assistant.id)
                yield {'event': 'delta', 'data': {'content': assistant.content}}
                yield {'event': 'done', 'data': {'message': AIMessageData.model_validate(assistant).model_dump(mode='json'), 'run_id': run_id}}
                return
            await asyncio.sleep(0.1)
    finally:
        # Disconnect stops this transport; the independent run remains auditable.
        if not task.done():
            task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
