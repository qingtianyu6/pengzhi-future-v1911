import os
from pathlib import Path
import subprocess
import importlib.util
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, func
from app.greenhouse_sim.domain import (Environment, Actions, Safety, SCENARIOS, CONFIG, scenario, dynamics,
                                      decide, Experiment, compare)
from app.greenhouse_sim.protocol import encode, decode
from app.greenhouse_sim.device import MockSTM32, DeviceLink
from app.greenhouse_sim.runtime import Runtime, manager
from app.greenhouse_sim.bridge import SerialOwner, create_bridge
from app.database import SessionLocal
from app.models import SensorData
from app.models.greenhouse_sim import GreenhouseSimulationEvent

@pytest.mark.parametrize('field,value',[('air_temperature',61),('air_temperature',float('nan')),('air_humidity',-1),('soil_temperature',-11),('soil_moisture',101),('light_lux',100001),('air_humidity',float('inf'))])
def test_validation(field,value):
    with pytest.raises(ValidationError): Environment(**{field:value})

def test_scenarios_and_user_input():
    assert len(SCENARIOS)==6
    assert len({tuple(scenario(k).model_dump().values()) for k in SCENARIOS})==6
    env=Environment(air_temperature=35.2,soil_moisture=17)
    result=decide(env,Environment(),'threshold',Safety(),0)
    assert result['selected']['fan'] and result['selected']['pump']

def test_threshold_hysteresis_and_manual():
    s=Safety(); t=Environment()
    assert not decide(t,t,'threshold',s,0)['selected']['fan']
    assert decide(Environment(air_temperature=30),t,'threshold',s,5)['selected']['fan']
    assert decide(Environment(air_temperature=26.1),t,'threshold',s,10)['selected']['fan']
    assert not decide(Environment(air_temperature=24,air_humidity=60),t,'threshold',s,15)['selected']['fan']
    assert decide(t,t,'manual',s,20,Actions(led=True))['selected']['led']

def test_prediction_enumerates_and_depends_on_input():
    low=decide(scenario('dark'),Environment(),'predictive',Safety(),0)
    high=decide(Environment(light_lux=90000,air_temperature=40),Environment(),'predictive',Safety(),0)
    assert len(low['candidates'])==8 and len({c['score'] for c in low['candidates']})>1
    assert low['selected']['lamp'] and not high['selected']['lamp'] and high['selected']['fan']
    assert low['selected']==min(low['candidates'],key=lambda c:c['score'])['action']

def test_dynamics_bounds_and_effects():
    e=scenario('mixed')
    base=dynamics(e,Actions(),10)
    active=dynamics(e,Actions(fan=True,pump=True,lamp=True),10)
    assert active.air_temperature<base.air_temperature
    assert active.air_humidity<base.air_humidity
    assert active.soil_moisture>base.soil_moisture
    assert active.light_lux>base.light_lux
    for _ in range(1000): active=dynamics(active,Actions(pump=True,lamp=True),10)
    assert active.soil_moisture<=100 and active.light_lux<=100000
    with pytest.raises(ValueError): dynamics(e,Actions(),11)

def test_safety_pump_cooldown_switch_and_emergency():
    s=Safety()
    assert s.apply(Actions(fan=True,pump=True,lamp=True),0)[0].pump
    assert s.apply(Actions(),1)[0].fan  # minimum switch interval
    s=Safety();s.apply(Actions(pump=True),0)
    assert not s.apply(Actions(pump=True),8)[0].pump
    assert not s.apply(Actions(pump=True),10)[0].pump
    assert s.apply(Actions(pump=True),20)[0].pump
    assert s.apply(Actions(fan=True,lamp=True),21,emergency=True)[0].mask()==0
    s=Safety();s.apply(Actions(pump=True),0)
    result=decide(Environment(),Environment(),'manual',s,8,Actions(pump=True))
    assert not result['selected']['pump'] and not result['candidates'][0]['action']['pump']

@pytest.mark.parametrize('kind,args',[('ENV',(260,650,240,550,16000)),('SET',(15,4000,0)),('STOP',()),('PING',()),('ACK',('SET',3)),('ERR',(4,))])
def test_protocol(kind,args):
    data=encode(23,kind,*args)
    assert decode(data)==(23,kind,list(map(str,args)))
    with pytest.raises(ValueError): decode(data.replace(b'V1',b'V2'))
    with pytest.raises(ValueError): decode(data[:-1])
    with pytest.raises(ValueError): decode(b'x'*129+b'\n')

def test_mock_duplicate_lease_timeout_disconnect_recovery():
    clock=[0.0]; device=MockSTM32(lambda:clock[0]);link=DeviceLink(device)
    link.environment(Environment()); assert device.oled['air_temperature']==26
    link.command('SET',10,4000,1);assert link.confirmed['pump']
    old=encode(link.seq,'SET',10,4000,1)
    clock[0]=3;device.exchange(old)
    clock[0]=5;device.watchdog();assert device.safety.action.mask()==0  # retry did not extend lease
    assert decode(device.exchange(old))[2]==['SET','0']
    assert decode(device.exchange(encode(link.seq,'SET',8,4000,1)))[1]=='ERR'
    for fault in ('timeout','disconnect'):
        device.fault=fault
        with pytest.raises((TimeoutError,ConnectionError)):link.command('PING')
        assert not link.connected
    device.fault='none';link.command('STOP');assert link.connected and not link.last_ack['physical_verified']

def test_mock_pump_max_heartbeat_does_not_extend_on_time():
    clock=[0.0];device=MockSTM32(lambda:clock[0]);link=DeviceLink(device)
    for t in (0,2,4,6):
        clock[0]=t;link.command('SET',2,4000,0)
    clock[0]=8;device.watchdog();assert not device.safety.action.pump
    with pytest.raises(RuntimeError):link.command('SET',2,4000,0)
    clock[0]=20;link.command('SET',2,4000,0);assert device.safety.action.pump

def test_comparison_repeatable_and_no_fake_superiority():
    spec=Experiment(steps=20,seed=7)
    a=compare(spec);b=compare(spec)
    assert a==b and len(a['disturbances'])==20
    assert all(len(r['series'])==20 and r['on_seconds']['pump']<=40 for r in a['results'])
    assert a['label'].startswith('软件仿真')

def test_runtime_failure_shutdown_and_latched_estop():
    r=Runtime(persist=False);r.env=scenario('mixed');r.running=True;r.evaluate(2)
    assert r.decision and r.link.last_ack['mode']=='mock'
    r.link.device.fault='timeout';r.evaluate(2)
    assert not r.running and r.link.confirmed is None and r.link.status=='failed' and r.error
    r.stop(True);r.stop();assert r.emergency

def test_backend_full_flow_and_sensor_isolation(client):
    base='/api/greenhouse-demo';client.headers['X-Simulation-Session']='integration'
    with SessionLocal() as db: before=db.scalar(select(func.count()).select_from(SensorData))
    assert len(client.get(base+'/scenarios').json())==6
    saved=client.post(base+'/scenarios',json={'name':'自定义干热','environment':Environment(air_temperature=41).model_dump()}).json()
    assert client.put(base+'/state',json={'scenario_id':saved['id']}).json()['environment']['air_temperature']==41
    assert len(client.get(base+'/scenarios').json())==7
    assert client.put(base+'/state',json={'scenario_id':saved['id']},headers={'X-Simulation-Session':'not-owner'}).status_code==422
    for sid in SCENARIOS:
        assert client.put(base+'/state',json={'scenario_id':sid}).json()['scenario_id']==sid
    for mode in ('manual','threshold','predictive'):
        payload={'environment':scenario('mixed').model_dump(),'mode':mode}
        if mode=='manual':payload['manual']={'fan':True,'pump':False,'lamp':False,'led':True}
        assert client.put(base+'/state',json=payload).status_code==200
        data=client.post(base+'/operation',json={'action':'start'}).json()
        assert data['running'] and data['decision'] and data['device']['last_ack']['mode']=='mock'
        r=manager.runtimes['demo:integration']
        r.last_seen=__import__('time').monotonic();manager.tick()
        assert client.get(base+'/state').json()['simulation_time']>0
        assert not client.post(base+'/operation',json={'action':'pause'}).json()['running']
    assert client.post(base+'/experiment',json={'steps':10,'seed':42}).status_code==200
    assert client.put(base+'/state',json={'environment':{'light_lux':-1}}).status_code==422
    assert client.put(base+'/state',json={'scenario_id':'no-such'}).status_code==422
    for f in ('disconnect','timeout','none'):
        assert client.post(base+'/fault',json={'fault':f}).status_code==200
    assert client.post(base+'/operation',json={'action':'estop'}).json()['emergency']
    client.put(base+'/state',json={'mode':'threshold'})
    assert client.post(base+'/operation',json={'action':'start'}).status_code==409
    data=client.post(base+'/operation',json={'action':'reset'}).json()
    assert not data['emergency'] and data['simulation_time']==0
    assert len(client.get(base+'/records').json())>5
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SensorData))==before
        assert db.scalar(select(func.count()).select_from(GreenhouseSimulationEvent))>0

def test_auth_and_session_isolation(client,monkeypatch):
    assert client.get('/api/greenhouse-control/state',headers={'Authorization':''}).status_code==401
    a=client.get('/api/greenhouse-control/state');assert a.status_code==200
    client.put('/api/greenhouse-demo/state',json={'scenario_id':'hot'},headers={'X-Simulation-Session':'guest-a'})
    assert client.get('/api/greenhouse-demo/state',headers={'X-Simulation-Session':'guest-b'}).json()['scenario_id']=='normal'
    # REAL configuration can never change the public simulation transport.
    monkeypatch.setenv('GREENHOUSE_DEVICE_MODE','real')
    assert client.get('/api/greenhouse-demo/state',headers={'X-Simulation-Session':'real-proof'}).json()['device']['mode']=='mock'
    assert client.get('/api/greenhouse-demo/state',headers={'X-Simulation-Session':'../invalid'}).status_code==422

def test_idle_guard_stops_without_viewer():
    r=Runtime(persist=False);r.running=True;r.last_seen=-1000
    manager.runtimes['idle-test']=r
    manager.tick();assert not r.running and r.safety.action.mask()==0
    del manager.runtimes['idle-test']

def test_bridge_auth_fragmented_frame_timeout_reopen():
    class FakeSerial:
        def __init__(self,*a,**kw):self.is_open=True;self.parts=[]
        def write(self,frame):
            seq,kind,_=decode(frame);response=encode(seq,'ACK',kind,0)
            self.parts=[response[:8],response[8:]]
        def flush(self):pass
        def read_until(self,*a):return self.parts.pop(0) if self.parts else b''
        def close(self):self.is_open=False
    owner=SerialOwner('COM_TEST',timeout=.03,factory=FakeSerial)
    app=create_bridge(owner,'t'*32);c=TestClient(app)
    payload={'frame':encode(1,'PING').decode()}
    assert c.post('/exchange',json=payload).status_code==401
    r=c.post('/exchange',json=payload,headers={'Authorization':'Bearer '+'t'*32})
    assert r.status_code==200 and decode(r.json()['frame'].encode())[1]=='ACK'
    assert c.post('/exchange',json={'frame':'bad'},headers={'Authorization':'Bearer '+'t'*32}).status_code==422
    class Dead(FakeSerial):
        def read_until(self,*a):return b''
    owner.close();owner.factory=Dead
    with pytest.raises(TimeoutError):owner.exchange(encode(2,'PING'))
    assert owner.serial is None
    owner.factory=FakeSerial;assert decode(owner.exchange(encode(3,'PING')))[0]==3

@pytest.fixture(scope='module')
def firmware_host(tmp_path_factory):
    import ziglang
    zig=Path(ziglang.__file__).parent/'zig.exe'
    folder=Path(__file__).resolve().parents[2]/'firmware'/'greenhouse_stm32'
    exe=tmp_path_factory.mktemp('gh-c')/'control.exe'
    subprocess.run([str(zig),'cc','-std=c11','-Wall','-Wextra','-Werror','-DGH_OUTPUTS_CONFIRMED=1',
                    str(folder/'control.c'),str(folder/'host_harness.c'),'-o',str(exe)],check=True)
    locked=exe.with_name('locked.exe')
    subprocess.run([str(zig),'cc','-std=c11','-Wall','-Wextra','-Werror',str(folder/'control.c'),str(folder/'host_harness.c'),'-o',str(locked)],check=True)
    return exe

def test_actual_c_firmware_matches_mock_and_watchdogs(firmware_host):
    requests=[(0,'ENV',(260,650,240,550,16000)),(0,'SET',(10,4000,1)),
              (2000,'SET',(10,4000,1)),(4000,'SET',(10,4000,1)),(6000,'SET',(10,4000,1)),
              (8000,'PING',()),(8001,'SET',(10,4000,1)),(20001,'SET',(10,4000,1)),
              (25002,'PING',()),(25003,'STOP',()),(26000,'ENV',(999,0,240,550,16000))]
    data=b'';expected=[];clock=[0.0];mock=MockSTM32(lambda:clock[0])
    for i,(now,kind,args) in enumerate(requests,1):
        frame=encode(i,kind,*args);data+=str(now).encode()+b' '+frame;clock[0]=now/1000
        expected.append(mock.exchange(frame))
    p=subprocess.run([str(firmware_host)],input=data,capture_output=True,check=True)
    actual=p.stdout.replace(b'\r\n',b'\n').splitlines(keepends=True)
    assert actual==expected

def test_c_rejects_corruption_overflow_and_duplicate_sequence(firmware_host):
    frame=encode(1,'SET',8,4000,0)
    payload=b'0 '+frame+b'1000 '+frame+b'5000 '+frame
    payload+=b'6000 '+encode(1,'SET',9,4000,0)
    payload+=b'7000 '+encode(2,'SET','99999999999999999999',4000,0)
    payload+=b'8000 V1,3,PING*00\n'
    result=subprocess.run([str(firmware_host)],input=payload,capture_output=True,check=True).stdout.replace(b'\r\n',b'\n').splitlines()
    assert decode(result[0]+b'\n')[2]==['SET','8']
    assert decode(result[2]+b'\n')[2]==['SET','0']  # duplicate never renews lease
    assert decode(result[3]+b'\n')[1:] == ('ERR',['5'])
    assert decode(result[4]+b'\n')[1:] == ('ERR',['2'])
    assert result[5]==b'NO_RESPONSE'
