from dataclasses import dataclass
from itertools import product
import math
import random
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Environment(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    air_temperature: float = Field(26, ge=-10, le=60)
    air_humidity: float = Field(65, ge=0, le=100)
    soil_temperature: float = Field(24, ge=-10, le=60)
    soil_moisture: float = Field(55, ge=0, le=100)
    light_lux: float = Field(16000, ge=0, le=100000)

class Actions(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    fan: bool = False
    pump: bool = False
    lamp: bool = False
    led: bool = False
    def mask(self):
        return sum(int(getattr(self, n)) << i for i, n in enumerate(('fan', 'pump', 'lamp', 'led')))
    @classmethod
    def from_mask(cls, mask):
        if not 0 <= mask <= 15:
            raise ValueError('invalid output mask')
        return cls(**{n: bool(mask & (1 << i)) for i, n in enumerate(('fan', 'pump', 'lamp', 'led'))})

SCENARIOS = {
    'normal': ('正常环境', [26,65,24,55,16000]),
    'hot': ('高温环境', [38,60,30,48,22000]),
    'humid': ('高湿环境', [27,92,25,60,15000]),
    'dry': ('土壤干旱', [29,52,26,22,18000]),
    'dark': ('光照不足', [24,70,23,52,1800]),
    'mixed': ('多指标异常', [37,90,30,23,1500]),
}
def scenario(key):
    return Environment(**dict(zip(Environment.model_fields, SCENARIOS[key][1])))

@dataclass(frozen=True)
class ModelConfig:
    # Per-minute relaxation rates; deliberately uncalibrated demonstration model.
    outside_temperature: float = 23
    outside_humidity: float = 55
    outside_lux: float = 10000
    natural_air: float = .035
    ventilation: float = .42
    natural_humidity: float = .025
    ventilation_humidity: float = .55
    soil_coupling: float = .055
    irrigation: float = 15
    evaporation: float = .25
    lamp_lux: float = 17000
    light_response: float = 1.8
    lamp_heat: float = .6
    pump_max: float = 8
    pump_cooldown: float = 12
    min_switch: float = 4

CONFIG = ModelConfig()
def dynamics(env, action, dt, disturbance=0.0, cfg=CONFIG):
    if not math.isfinite(dt) or not 0 < dt <= 10:
        raise ValueError('simulation step must be (0,10] seconds')
    m = dt / 60
    e = env.model_dump()
    e['air_temperature'] += m * ((cfg.natural_air + cfg.ventilation*action.fan) *
        (cfg.outside_temperature + disturbance - env.air_temperature) + cfg.lamp_heat*action.lamp)
    e['air_humidity'] += m * ((cfg.natural_humidity + cfg.ventilation_humidity*action.fan) *
        (cfg.outside_humidity - env.air_humidity) + .8*action.pump)
    e['soil_temperature'] += m * cfg.soil_coupling*(env.air_temperature-env.soil_temperature)
    e['soil_moisture'] += m * (cfg.irrigation*action.pump-cfg.evaporation*(1+action.fan))
    desired_light = max(0, cfg.outside_lux + disturbance*500) + cfg.lamp_lux*action.lamp
    e['light_lux'] += (desired_light-env.light_lux) * (1-math.exp(-cfg.light_response*m))
    for k, v in e.items():
        field = Environment.model_fields[k]
        low = next(x.ge for x in field.metadata if hasattr(x, 'ge'))
        high = next(x.le for x in field.metadata if hasattr(x, 'le'))
        e[k] = round(max(low, min(high, v)), 4)
    return Environment(**e)

class Safety:
    def __init__(self):
        self.action = Actions()
        self.changed = dict.fromkeys(('fan','pump','lamp','led'), -1000.0)
        self.pump_since = None
        self.pump_off = -1000.0
    def feasible(self, a, now):
        if a.pump and ((self.pump_since is not None and now-self.pump_since >= CONFIG.pump_max)
                       or (not self.action.pump and now-self.pump_off < CONFIG.pump_cooldown)):
            return False
        return all(getattr(a,n)==getattr(self.action,n) or now-self.changed[n]>=CONFIG.min_switch
                   for n in ('fan','lamp'))
    def apply(self, requested, now, emergency=False):
        a = requested.model_copy()
        reasons = []
        if emergency:
            a = Actions()
        else:
            for n in ('fan','lamp'):
                if getattr(a,n)!=getattr(self.action,n) and now-self.changed[n]<CONFIG.min_switch:
                    setattr(a,n,getattr(self.action,n)); reasons.append(n+' 最小启停间隔')
            if a.pump and not self.feasible(a, now):
                a.pump=False; reasons.append('水泵时长/冷却限制')
        for n in self.changed:
            if getattr(a,n)!=getattr(self.action,n):
                self.changed[n]=now
        if a.pump and not self.action.pump:
            self.pump_since=now
        if not a.pump and self.action.pump:
            self.pump_since=None; self.pump_off=now
        self.action=a
        return a, reasons

SCALES = dict(air_temperature=4, air_humidity=15, soil_temperature=5, soil_moisture=15, light_lux=15000)
def deviation(env, target):
    return sum(((getattr(env,k)-getattr(target,k))/s)**2 for k,s in SCALES.items())

def decide(env, target, mode, safety, now, manual=None):
    constraints = ['水泵连续≤8秒，停机冷却≥12秒', '风扇/灯光启停间隔≥4秒', '仅软件仿真模型，未经实棚标定']
    candidates=[]
    if mode == 'manual':
        chosen=manual or Actions()
        reason='手动接管；统一执行安全限制'
    elif mode == 'threshold':
        old=safety.action
        chosen=Actions(
            fan=(env.air_temperature>target.air_temperature+1 or env.air_humidity>target.air_humidity+5
                 or (old.fan and (env.air_temperature>target.air_temperature-.5 or env.air_humidity>target.air_humidity-2))),
            pump=(env.soil_moisture<target.soil_moisture-4 or (old.pump and env.soil_moisture<target.soil_moisture)),
            lamp=(env.light_lux<target.light_lux-2000 or (old.lamp and env.light_lux<target.light_lux+1000)), led=True)
        reason='规则控制：温湿度/含水率/光照与目标比较，使用滞回带'
    else:
        for bits in product((False,True), repeat=3):
            a=Actions(fan=bits[0], pump=bits[1], lamp=bits[2], led=True)
            if not safety.feasible(a, now):
                continue
            future=env.model_copy(); virtual=Safety()
            virtual.action=safety.action.model_copy(); virtual.changed=safety.changed.copy()
            virtual.pump_since=safety.pump_since; virtual.pump_off=safety.pump_off
            score=0; energy=0
            # Receding horizon: evaluate each constant requested action through the safety dynamics.
            for step in range(12):
                applied,_=virtual.apply(a,now+step*2)
                future=dynamics(future,applied,2)
                score+=deviation(future,target)/12
                energy+=(.7*applied.fan+.4*applied.pump+applied.lamp)*2/60
            switches=sum(getattr(a,n)!=getattr(safety.action,n) for n in ('fan','pump','lamp'))
            score += .025*energy + .015*switches
            candidates.append({'action':a.model_dump(),'score':round(score,6),'predicted':future.model_dump()})
        best=min(candidates,key=lambda x:x['score'])
        chosen=Actions(**best['action'])
        reason=f"预测优化：枚举{len(candidates)}个可行动作，24秒时域，最小代价{best['score']:.4f}；包含偏差、能耗与启停惩罚"
    applied, limits=safety.apply(chosen,now)
    if not candidates:
        candidates=[{'action':applied.model_dump(), 'score':None}]
    return {'requested':chosen.model_dump(), 'selected':applied.model_dump(), 'candidates':candidates,
            'reason':reason, 'constraints':constraints+limits, 'next_evaluation_seconds':2,
            'environment':env.model_dump(), 'target':target.model_dump(), 'mode':mode}

class Experiment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    initial: Environment = Field(default_factory=lambda: scenario('mixed'))
    target: Environment = Field(default_factory=Environment)
    seed: int = Field(42, ge=0, le=2147483647)
    steps: int = Field(120,ge=10,le=600)

def compare(spec):
    rng=random.Random(spec.seed)
    disturbances=[rng.uniform(-1,1) for _ in range(spec.steps)]
    rows=[]
    for mode in ('threshold','predictive'):
        env=spec.initial.model_copy(); safety=Safety(); total=0; energy=0; switches=0
        durations=dict(fan=0,pump=0,lamp=0); series=[]
        for i,d in enumerate(disturbances):
            old=safety.action
            result=decide(env,spec.target,mode,safety,i*2)
            a=Actions(**result['selected'])
            switches+=sum(getattr(old,k)!=getattr(a,k) for k in durations)
            for k in durations: durations[k]+=int(getattr(a,k))*2
            energy+=(.7*a.fan+.4*a.pump+a.lamp)*2/60
            env=dynamics(env,a,2,d); total+=deviation(env,spec.target)
            series.append({'time':(i+1)*2, **env.model_dump(), 'action':a.model_dump()})
        rows.append({'mode':mode,'mean_target_deviation':total/spec.steps,'control_steps':spec.steps,
                     'on_seconds':durations,'switches':switches,'energy_proxy':energy,
                     'irrigation_seconds':durations['pump'],'series':series})
    return {'label':'软件仿真对比结果，非真实温室实验', 'parameters':spec.model_dump(),
            'disturbances':disturbances,'model':CONFIG.__dict__, 'results':rows}
