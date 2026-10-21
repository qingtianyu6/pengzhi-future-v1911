import os
import re
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.database import SessionLocal
from app.models.greenhouse_sim import GreenhouseSimulationEvent, GreenhouseSimulationScenario
from app.services.access import business_access, actor
from app.greenhouse_sim.domain import Environment, Actions, Experiment, SCENARIOS, scenario, compare
from app.greenhouse_sim.runtime import manager

router=APIRouter(tags=['棚智自治'])
class Update(BaseModel):
    model_config=ConfigDict(extra='forbid')
    environment: Environment | None=None
    target: Environment | None=None
    scenario_id: str | None=Field(None,max_length=60)
    mode: Literal['manual','threshold','predictive'] | None=None
    manual: Actions | None=None
class CustomScenario(BaseModel):
    model_config=ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str=Field(min_length=1,max_length=60)
    environment: Environment

class Operation(BaseModel):
    action: Literal['start','pause','reset','estop','evaluate']
class Fault(BaseModel):
    fault: Literal['none','disconnect','timeout']

def demo(x_simulation_session: str=Header('local-demo')):
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,64}',x_simulation_session):
        raise HTTPException(422,'无效模拟会话')
    try: return manager.get('demo:'+x_simulation_session)  # Never selects real, regardless of environment.
    except ValueError as exc: raise HTTPException(409,str(exc))
def protected(_=Depends(business_access)):
    user=actor()
    mode=os.getenv('GREENHOUSE_DEVICE_MODE','mock').lower()
    if mode not in ('mock','real'): raise HTTPException(503,'设备模式配置错误')
    try: return manager.get(f'user:{user.organization_id}:{user.id}',user.id,real=mode=='real')
    except ValueError as exc: raise HTTPException(409,str(exc))

def mount(prefix,dependency):
    sub=APIRouter(prefix=prefix)
    @sub.get('/state')
    def state(r=Depends(dependency)):
        return r.snapshot()
    @sub.get('/scenarios')
    def scenarios(r=Depends(dependency)):
        with SessionLocal() as db:
            custom=db.scalars(select(GreenhouseSimulationScenario).where(
                GreenhouseSimulationScenario.session_key==r.key).order_by(GreenhouseSimulationScenario.id)).all()
            return [{'id':k,'name':v[0],'environment':scenario(k).model_dump()} for k,v in SCENARIOS.items()]+[
                {'id':'custom-'+str(s.id),'name':s.name,'environment':s.environment} for s in custom]
    @sub.post('/scenarios')
    def save_scenario(data:CustomScenario,r=Depends(dependency)):
        with r.lock, SessionLocal() as db:
            count=len(db.scalars(select(GreenhouseSimulationScenario.id).where(GreenhouseSimulationScenario.session_key==r.key)).all())
            if count>=30: raise HTTPException(409,'每个会话最多保存30个自定义场景')
            item=GreenhouseSimulationScenario(session_key=r.key,name=data.name,environment=data.environment.model_dump())
            db.add(item); db.commit(); db.refresh(item)
            return {'id':'custom-'+str(item.id),'name':item.name,'environment':item.environment}
    @sub.put('/state')
    def update(data:Update,r=Depends(dependency)):
        with r.lock:
            custom_env=None
            if data.scenario_id and data.scenario_id not in SCENARIOS and data.scenario_id!='custom':
                if not re.fullmatch(r'custom-[0-9]+',data.scenario_id): raise HTTPException(422,'未知场景')
                with SessionLocal() as db:
                    item=db.scalar(select(GreenhouseSimulationScenario).where(
                        GreenhouseSimulationScenario.id==int(data.scenario_id[7:]),
                        GreenhouseSimulationScenario.session_key==r.key))
                    if not item: raise HTTPException(422,'未知场景')
                    custom_env=Environment(**item.environment)
            # Changing inputs/mode stops existing output first; new control always recomputes.
            r.stop()
            if data.scenario_id:
                r.scenario_id=data.scenario_id
                if data.scenario_id in SCENARIOS: r.env=scenario(data.scenario_id)
            if custom_env is not None: r.env=custom_env
            if data.environment:
                r.env=data.environment; r.scenario_id='custom' if not data.scenario_id else data.scenario_id
            if data.target: r.target=data.target
            if data.mode: r.mode=data.mode
            if data.manual: r.manual=data.manual; r.mode='manual'
            r.humidity_baseline=abs(r.env.air_humidity-r.target.air_humidity)
            r.record('input_updated')
            return r.snapshot()
    @sub.post('/operation')
    def operation(data:Operation,r=Depends(dependency)):
        with r.lock:
            if data.action in ('pause','estop'): r.stop(data.action=='estop')
            elif data.action=='reset':
                r.stop(); r.emergency=False; r.env=scenario('normal'); r.scenario_id='normal'
                r.simulation_time=0; r.history.clear(); r.mode='threshold'; r.manual=Actions(); r.decision=None
                r.humidity_baseline=abs(r.env.air_humidity-r.target.air_humidity)
                r.record('reset')
            else:
                if r.emergency: raise HTTPException(409,'急停已锁定，请先重置')
                r.running=data.action=='start'
                r.last_seen=__import__('time').monotonic()
                r.evaluate()
            return r.snapshot()
    @sub.post('/fault')
    def fault(data:Fault,r=Depends(dependency)):
        if r.link.device.mode!='mock': raise HTTPException(403,'仅虚拟设备允许故障注入')
        with r.lock:
            r.link.device.fault=data.fault
            if data.fault!='none': r.stop(); r.link.connected=False
            else:
                try: r.link.command('STOP')
                except Exception as exc: r.error=str(exc)
                else: r.error=None
            r.record('fault_changed')
            return r.snapshot()
    @sub.post('/experiment')
    def experiment(spec:Experiment,r=Depends(dependency)):
        return compare(spec)  # Local plant only; no device side effects.
    @sub.get('/records')
    def records(r=Depends(dependency)):
        with SessionLocal() as db:
            rows=db.scalars(select(GreenhouseSimulationEvent).where(
                GreenhouseSimulationEvent.session_key==r.key).order_by(GreenhouseSimulationEvent.id.desc()).limit(100))
            return [row.payload for row in rows]
    router.include_router(sub)
mount('/greenhouse-demo',demo)
mount('/greenhouse-control',protected)
