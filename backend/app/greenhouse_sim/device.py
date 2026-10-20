from collections import deque, OrderedDict
import os
import secrets
import time
import httpx
from .domain import Actions, Environment, Safety
from .protocol import encode, decode

class MockSTM32:
    mode='mock'
    def __init__(self, clock=time.monotonic):
        self.clock=clock; self.safety=Safety(); self.oled=None; self.fault='none'
        self.last_rx=clock(); self.lease=0; self.cache=OrderedDict(); self.takeover=False
    def watchdog(self):
        now=self.clock()
        if now-self.last_rx>self.lease:
            self.safety.apply(Actions(),now,emergency=True)
        elif self.safety.pump_since is not None and now-self.safety.pump_since>=8:
            desired=self.safety.action.model_copy(); desired.pump=False
            self.safety.apply(desired,now,emergency=True) if not desired.mask() else self.safety.apply(desired,now)
    def exchange(self, frame):
        self.watchdog()
        if self.fault=='disconnect': raise ConnectionError('虚拟串口已断开')
        if self.fault=='timeout': raise TimeoutError('虚拟回执超时')
        seq,kind,args=decode(frame)
        if seq in self.cache:
            old,response=self.cache[seq]
            if old!=frame: return encode(seq,'ERR',5)
            # Duplicate is never reapplied and does not extend lease.
            cached_seq,cached_kind,cached_args=decode(response)
            return encode(seq,'ACK',cached_args[0],self.safety.action.mask()) if cached_kind=='ACK' else response
        try:
            if kind=='ENV' and len(args)==5:
                vals=[int(x) for x in args]
                self.oled=Environment(**dict(zip(Environment.model_fields,[v/10 for v in vals[:4]]+[vals[4]]))).model_dump()
            elif kind=='SET' and len(args)==3:
                mask,lease,takeover=map(int,args)
                if not 100<=lease<=5000 or takeover not in (0,1): raise ValueError('range')
                desired=Actions.from_mask(mask)
                if not self.safety.feasible(desired,self.clock()):
                    response=encode(seq,'ERR',4)
                    self.cache[seq]=(frame,response)
                    if len(self.cache)>8: self.cache.popitem(last=False)
                    return response
                self.safety.apply(desired,self.clock()); self.lease=lease/1000; self.takeover=bool(takeover)
                self.last_rx=self.clock()
            elif kind=='STOP' and not args:
                self.safety.apply(Actions(),self.clock(),emergency=True); self.takeover=True
            elif kind=='PING' and not args:
                pass
            else: raise ValueError('arguments')
            response=encode(seq,'ACK',kind,self.safety.action.mask())
        except ValueError:
            response=encode(seq,'ERR',2)
        self.cache[seq]=(frame,response)
        if len(self.cache)>8: self.cache.popitem(last=False)
        return response
    def close(self): self.safety.apply(Actions(),self.clock(),emergency=True)

class BridgeDevice:
    mode='real'
    def __init__(self):
        url=os.getenv('GREENHOUSE_BRIDGE_URL','http://127.0.0.1:8766')
        from urllib.parse import urlparse
        p=urlparse(url)
        if p.hostname not in ('127.0.0.1','localhost','::1') or p.scheme!='http':
            raise ValueError('桥接地址必须为本机 HTTP；WSL 请使用 localhost 转发')
        self.url=url; self.token=os.getenv('GREENHOUSE_BRIDGE_TOKEN','')
    def exchange(self, frame):
        if not self.token: raise ConnectionError('未配置串口桥接令牌')
        r=httpx.post(self.url+'/exchange',json={'frame':frame.decode('ascii')},
                     headers={'Authorization':'Bearer '+self.token},timeout=4,trust_env=False)
        r.raise_for_status()
        return r.json()['frame'].encode('ascii')
    def close(self): pass

class DeviceLink:
    def __init__(self, device):
        self.device=device; self.seq=secrets.randbelow(1000000000)+1
        self.logs=deque(maxlen=200); self.connected=False; self.last_ack=None
        self.status='planned'; self.confirmed=None
    def command(self, kind, *args):
        self.seq=self.seq%2147483647+1
        frame=encode(self.seq,kind,*args)
        self.status='planned'
        for attempt in range(2):
            self.logs.append({'time':time.time(),'direction':'TX','frame':frame.decode().strip(),'attempt':attempt+1})
            self.status='sent'
            try:
                response=self.device.exchange(frame)
                self.logs.append({'time':time.time(),'direction':'RX','frame':response.decode().strip()})
                seq,k,args=decode(response)
                if seq!=self.seq: raise ValueError('回执编号不匹配')
                if k=='ERR': raise RuntimeError('设备拒绝命令，错误码 '+','.join(args))
                if k!='ACK' or len(args)!=2 or args[0]!=kind: raise ValueError('无效 ACK')
                self.confirmed=Actions.from_mask(int(args[1])).model_dump()
                self.last_ack={'sequence':seq,'type':kind,'mode':self.device.mode,'at':time.time(),
                               'gpio':self.confirmed,'physical_verified':False}
                self.connected=True; self.status='mock_confirmed' if self.device.mode=='mock' else 'gpio_confirmed'
                return self.last_ack
            except Exception as exc:
                self.connected=False; self.status='failed'; self.confirmed=None
                self.logs.append({'time':time.time(),'direction':'ERROR','frame':str(exc)})
                if not isinstance(exc,(TimeoutError,ConnectionError,httpx.TransportError)) or attempt:
                    raise
    def environment(self, env):
        values=list(env.model_dump().values())
        return self.command('ENV',*(round(x*10) for x in values[:4]), round(values[4]))
