import asyncio
from collections import deque
import os
import threading
import time
from sqlalchemy import select
from app.database import SessionLocal
from app.models.greenhouse_sim import GreenhouseSimulationEvent
from .domain import Environment, Actions, Safety, scenario, decide, dynamics
from .device import DeviceLink, MockSTM32, BridgeDevice

class Runtime:
    def __init__(self,key='test',owner=None,device=None,persist=True):
        self.key=key; self.owner=owner; self.link=DeviceLink(device or MockSTM32())
        self.persist=persist; self.lock=threading.RLock(); self.safety=Safety()
        self.env=scenario('normal'); self.target=Environment(); self.scenario_id='normal'
        self.humidity_baseline=abs(self.env.air_humidity-self.target.air_humidity)
        self.mode='threshold'; self.running=False; self.simulation_time=0; self.manual=Actions()
        self.decision=None; self.error=None; self.history=deque(maxlen=300); self.events=deque(maxlen=100)
        self.last_seen=time.monotonic(); self.emergency=False
        self.record('created')
    def record(self,event):
        payload={'event':event,'at':time.time(),'environment':self.env.model_dump(),'target':self.target.model_dump(),
                 'scenario_id':self.scenario_id,'simulation_time':self.simulation_time,'mode':self.mode,
                 'decision':self.decision,'command_status':self.link.status,'ack':self.link.last_ack,'error':self.error,
                 'wire_transactions':list(self.link.logs)[-8:]}
        self.events.appendleft(payload)
        if self.persist:
            with SessionLocal() as db:
                db.add(GreenhouseSimulationEvent(session_key=self.key,owner_user_id=self.owner,event=event,payload=payload))
                db.commit()
    def snapshot(self):
        with self.lock:
            self.last_seen=time.monotonic()
            return {'source':'simulation','environment':self.env.model_dump(),'target':self.target.model_dump(),
                    'scenario_id':self.scenario_id,'simulation_time':self.simulation_time,'mode':self.mode,
                    'running':self.running,'emergency':self.emergency,'decision':self.decision,
                    'humidity_baseline':self.humidity_baseline,
                    'planned':self.safety.action.model_dump(),'device':{
                        'mode':self.link.device.mode,'connected':self.link.connected,'status':self.link.status,
                        'confirmed':self.link.confirmed,'last_ack':self.link.last_ack,'physical_verified':False,
                        'oled':getattr(self.link.device,'oled',None),'fault':getattr(self.link.device,'fault',None)},
                    'error':self.error,'history':list(self.history),'events':list(self.events),'wire_logs':list(self.link.logs)}
    def stop(self,emergency=False):
        self.running=False; self.emergency=self.emergency or emergency
        self.safety.apply(Actions(),time.monotonic(),emergency=True)
        try:
            self.link.command('STOP'); self.error=None
        except Exception as exc: self.error=str(exc)
        self.record('emergency_stop' if emergency else 'paused')
    def evaluate(self,dt=0):
        if self.emergency: raise ValueError('急停已锁定，请先重置')
        now=time.monotonic()
        self.decision=decide(self.env,self.target,self.mode,self.safety,now,self.manual)
        action=Actions(**self.decision['selected'])
        try:
            self.link.environment(self.env)
            self.link.command('SET',action.mask(),4000,int(self.mode=='manual'))
            self.error=None
        except Exception as exc:
            self.error=str(exc); self.running=False
            self.safety.apply(Actions(),now,emergency=True)
            # A lost ACK leaves hardware state unknown; try STOP, never report physical success.
            try: self.link.command('STOP')
            except Exception: pass
            self.link.connected=False; self.link.confirmed=None; self.link.status='failed'
        # Only acknowledged simulated GPIO contributes to the software plant.
        if dt:
            applied=Actions(**self.link.confirmed) if self.link.confirmed else Actions()
            self.env=dynamics(self.env,applied,dt)
            self.simulation_time+=dt
            self.history.append({'time':self.simulation_time, **self.env.model_dump()})
        self.record('decision')

class Manager:
    IDLE_TTL = 15 * 60

    def _reap_idle(self):
        # Caller holds manager.lock. Real device ownership is never recycled here.
        now = time.monotonic()
        for key, r in list(self.runtimes.items()):
            with r.lock:
                if isinstance(r.link.device, MockSTM32) and not r.running and now-r.last_seen > self.IDLE_TTL:
                    r.stop()
                    r.link.device.close()
                    del self.runtimes[key]

    def __init__(self): self.runtimes={}; self.lock=threading.RLock(); self.real_owner=None
    def get(self,key,owner=None,real=False):
        with self.lock:
            self._reap_idle()
            if key not in self.runtimes:
                if len(self.runtimes)>=64: raise ValueError('模拟会话暂满，请稍后重试，闲置会话将自动释放')
                if real:
                    if self.real_owner is not None and self.real_owner!=key: raise ValueError('真实串口已由其他控制会话独占')
                    if os.getenv('GREENHOUSE_REAL_ENABLED')!='YES_PINS_VERIFIED':
                        raise ValueError('真实输出未启用：完成引脚确认后配置 GREENHOUSE_REAL_ENABLED')
                    device=BridgeDevice(); self.real_owner=key
                else: device=MockSTM32()
                self.runtimes[key]=Runtime(key,owner,device)
            self.runtimes[key].last_seen=time.monotonic()
            return self.runtimes[key]
    def tick(self):
        with self.lock: items=list(self.runtimes.values())
        for r in items:
            with r.lock:
                if r.running:
                    if time.monotonic()-r.last_seen>15:
                        r.stop(); continue
                    try: r.evaluate(2)
                    except Exception as exc:
                        r.error=str(exc); r.running=False
                        r.safety.apply(Actions(),time.monotonic(),emergency=True)
                        try: r.link.command('STOP')
                        except Exception: pass
                elif isinstance(r.link.device,MockSTM32):
                    r.link.device.watchdog()
                    r.link.confirmed=r.link.device.safety.action.model_dump() if r.link.connected else None
                elif r.link.last_ack and time.time()-r.link.last_ack['at']>4:
                    r.link.confirmed=None; r.link.status='expired'
        with self.lock: self._reap_idle()

    def close(self):
        for r in list(self.runtimes.values()):
            with r.lock: r.stop(); r.link.device.close()
        self.runtimes.clear(); self.real_owner=None

manager=Manager()
async def worker():
    try:
        while True:
            await asyncio.sleep(2)
            await asyncio.to_thread(manager.tick)
    finally:
        await asyncio.to_thread(manager.close)
