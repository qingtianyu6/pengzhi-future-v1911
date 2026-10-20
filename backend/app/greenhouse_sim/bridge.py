"""Windows-only serial owner; local bearer-authenticated HTTP bridge (also reachable via WSL localhost forwarding)."""
from collections import deque
import hmac
import os
import threading
import time
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .protocol import decode, MAX_FRAME

class SerialOwner:
    def __init__(self,port,baud=115200,timeout=.8,factory=None):
        self.port=port; self.baud=baud; self.timeout=timeout; self.factory=factory
        self.serial=None; self.lock=threading.Lock(); self.logs=deque(maxlen=500)
    def close(self):
        if self.serial:
            self.serial.close(); self.serial=None
    def exchange(self,frame):
        wanted,kind,_=decode(frame)
        with self.lock:
            try:
                if self.serial is None or not self.serial.is_open:
                    if self.factory is None:
                        import serial
                        self.factory=serial.Serial
                    # Windows CreateFile opens COM handles exclusively; second owner fails.
                    self.serial=self.factory(self.port,self.baud,timeout=.1,write_timeout=self.timeout)
                self.logs.append({'at':time.time(),'direction':'TX','frame':frame.decode().strip()})
                self.serial.write(frame); self.serial.flush()
                deadline=time.monotonic()+self.timeout
                pending=bytearray(); dropping=False
                while time.monotonic()<deadline:
                    chunk=self.serial.read_until(b'\n',MAX_FRAME+1)
                    if not chunk: continue
                    pending.extend(chunk)
                    if len(pending)>MAX_FRAME: dropping=True
                    if not pending.endswith(b'\n'):
                        if dropping: pending.clear()
                        continue
                    reply=bytes(pending); pending.clear()
                    if dropping: dropping=False; continue
                    self.logs.append({'at':time.time(),'direction':'RX','frame':reply.decode('ascii',errors='replace').strip()})
                    try: seq,typ,args=decode(reply)
                    except ValueError: continue
                    if seq==wanted and (typ=='ERR' or (typ=='ACK' and args and args[0]==kind)):
                        return reply
                raise TimeoutError('STM32 ACK timeout')
            except Exception as exc:
                self.logs.append({'at':time.time(),'direction':'ERROR','frame':str(exc)})
                self.close()
                raise

def create_bridge(owner=None, token=None):
    app=FastAPI(title='棚智未来本机串口桥',docs_url=None,redoc_url=None)
    owner=owner or SerialOwner(os.getenv('GREENHOUSE_SERIAL_PORT','COM3'),int(os.getenv('GREENHOUSE_SERIAL_BAUD','115200')))
    token=token or os.getenv('GREENHOUSE_BRIDGE_TOKEN','')
    if len(token)<24: raise ValueError('桥接令牌至少24字符；请使用 start_serial_bridge.ps1')
    def authorize(authorization):
        if not hmac.compare_digest(authorization or '', 'Bearer '+token): raise HTTPException(401,'本机桥接授权失败')
    class Frame(BaseModel):
        frame: str=Field(max_length=MAX_FRAME)
    # Avoid postponed annotations: FastAPI resolves this local model directly.
    @app.post('/exchange')
    def exchange(data:Frame,authorization:str | None=Header(None)):
        authorize(authorization)
        try:
            wire=data.frame.encode('ascii'); _,kind,_=decode(wire)
            if kind not in ('ENV','SET','STOP','PING'): raise ValueError('not a request')
            return {'frame':owner.exchange(wire).decode('ascii')}
        except (ValueError,UnicodeError) as exc: raise HTTPException(422,str(exc))
        except Exception as exc: raise HTTPException(503,str(exc))
    @app.get('/status')
    def status(authorization:str | None=Header(None)):
        authorize(authorization)
        return {'port':owner.port,'baud':owner.baud,'connected':bool(owner.serial and owner.serial.is_open),'logs':list(owner.logs)}
    return app
