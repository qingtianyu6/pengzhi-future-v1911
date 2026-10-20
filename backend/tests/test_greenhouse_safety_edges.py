from pathlib import Path
import importlib.util
import subprocess
import pytest
from app.greenhouse_sim.device import MockSTM32
from app.greenhouse_sim.protocol import encode, decode
from app.greenhouse_sim.domain import Actions

def test_mock_rejected_command_stays_rejected_on_retry():
    clock=[0.0];m=MockSTM32(lambda:clock[0])
    m.exchange(encode(1,'SET',2,4000,0))
    clock[0]=3;m.exchange(encode(2,'STOP'))
    clock[0]=4;request=encode(3,'SET',2,4000,0)
    rejected=m.exchange(request);assert decode(rejected)[1:] == ('ERR',['4'])
    clock[0]=20;assert m.exchange(request)==rejected
    assert decode(m.exchange(encode(4,'SET',2,4000,0)))[1]=='ACK'

def test_observer_cannot_control_and_real_requires_verified_pins(client,monkeypatch):
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.models import User
    monkeypatch.setenv('GREENHOUSE_DEVICE_MODE','real')
    monkeypatch.delenv('GREENHOUSE_REAL_ENABLED',raising=False)
    assert client.get('/api/greenhouse-control/state').status_code==409
    monkeypatch.setenv('GREENHOUSE_DEVICE_MODE','mock')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.phone=='13900000000'))
        user.role='observer';db.commit()
    assert client.get('/api/greenhouse-control/state').status_code==200
    assert client.post('/api/greenhouse-control/operation',json={'action':'start'}).status_code==403
    assert client.put('/api/greenhouse-control/state',json={'mode':'manual'}).status_code==403

def test_firmware_default_lock(tmp_path):
    import ziglang
    root=Path(__file__).resolve().parents[2]
    folder=root/'firmware'/'greenhouse_stm32';zig=Path(ziglang.__file__).parent/'zig.exe'
    exe=tmp_path/'locked.exe'
    subprocess.run([str(zig),'cc','-std=c11','-Wall','-Wextra','-Werror',str(folder/'control.c'),str(folder/'host_harness.c'),'-o',str(exe)],check=True)
    data=b''.join(str(i*5000).encode()+b' '+encode(i+1,'SET',mask,4000,0) for i,mask in enumerate((1,2,4,7,8)))
    replies=subprocess.run([str(exe)],input=data,capture_output=True,check=True).stdout.replace(b'\r\n',b'\n').splitlines()
    assert all(decode(r+b'\n')[1:]==('ERR',['3']) for r in replies[:4])
    assert decode(replies[4]+b'\n')[2]==['SET','8']
