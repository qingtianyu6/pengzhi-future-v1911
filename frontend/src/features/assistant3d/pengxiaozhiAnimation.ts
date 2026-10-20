import { MathUtils } from 'three'
import type { RobotRig } from './pengxiaozhiModel'

export type RobotAction = 'idle' | 'blink' | 'wave' | 'stretch' | 'sitting' | 'dozing' | 'greeting' | 'thinking' | 'reminder' | 'complete' | 'unavailable' | 'listening' | 'speaking'
export type LookTarget = { x: number; y: number; active: boolean }

/** Blended joint targets, rather than replacement pictures. Interruptions keep the current joint pose. */
export function createRobotAnimator(rig: RobotRig) {
  let time=0
  let sit=0,wave=0,stretch=0,doze=0,think=0,listen=0,speak=0,remind=0,happy=0,blink=0,lookX=0,lookY=0
  const velocities: Record<string,number> = {}
  function update(action:RobotAction,delta:number,look:LookTarget={x:0,y:0,active:false},still=false) {
    const dt=Math.min(Math.max(delta,0),.08)
    if(!still) time+=dt
    const blend=(value:number,target:number,speed=5)=>MathUtils.damp(value,target,speed,dt)
    // Exact critically damped springs preserve both pose and velocity on interruption.
    const spring=(key:string,value:number,target:number,omega:number)=>{
      const velocity=velocities[key]??0,offset=value-target
      const decay=Math.exp(-omega*dt),travel=(velocity+omega*offset)*dt
      velocities[key]=(velocity-omega*travel)*decay
      return target+(offset+travel)*decay
    }
    sit=spring('sit',sit,!still&&(action==='sitting'||action==='dozing')?1:0,6.4)
    // A seated character first unfolds its legs; greeting is delayed until mostly upright.
    const upright=1-MathUtils.smoothstep(sit,.12,.72)
    wave=spring('wave',wave,!still&&(action==='wave'||action==='greeting')?upright:0,10)
    stretch=spring('stretch',stretch,!still&&action==='stretch'?upright:0,7)
    doze=blend(doze,!still&&action==='dozing'?1:0,4)
    think=blend(think,!still&&action==='thinking'?1:0,5)
    listen=blend(listen,!still&&action==='listening'?1:0,5)
    speak=blend(speak,!still&&action==='speaking'?1:0,6)
    remind=blend(remind,!still&&action==='reminder'?1:0,5)
    happy=blend(happy,!still&&action==='complete'?1:0,5)
    blink=blend(blink,!still&&action==='blink'?1:0,35)
    lookX=blend(lookX,!still&&look.active?MathUtils.clamp(look.x,-1,1):0,7)
    lookY=blend(lookY,!still&&look.active?MathUtils.clamp(look.y,-1,1):0,7)
    const phase=still?0:time
    const breath=Math.sin(phase*1.8)
    const hip=-1.90*sit,knee=.80*sit
    rig.legs.forEach(({hip:h,knee:k,ankle},i)=>{
      h.rotation.x=hip;k.rotation.x=knee;ankle.rotation.x=-hip-knee
      h.rotation.z=(i===0?-.025:.025)*(1-sit)
    })
    // Analytic leg height maintains the sole at floor level throughout the sitting transition.
    rig.pelvis.position.y=.31+rig.legLengths.upper*Math.cos(hip)+rig.legLengths.lower*Math.cos(hip+knee)
    rig.pelvis.position.z=-.20*sit
    rig.torso.position.y=still?0:.006*breath
    rig.torso.rotation.x=.07*sit+.035*doze
    rig.torso.rotation.z=(still?0:.013*Math.sin(phase*.8))+.055*Math.sin(phase*1.5)*stretch
    rig.head.rotation.y=blend(rig.head.rotation.y,lookX*.26+.025*Math.sin(phase*.65)*(1-doze),9)
    rig.head.rotation.x=blend(rig.head.rotation.x,lookY*.14+.13*doze-.04*sit-.08*listen+.022*Math.sin(phase*3)*speak+.035*Math.sin(phase*2.5)*happy,9)
    rig.head.rotation.z=blend(rig.head.rotation.z,-.06-.04*think-.07*listen+.035*Math.sin(phase*1.2)*doze,9)
    rig.arms.forEach(({shoulder,elbow,wrist},i)=>{
      const side=i===0?-1:1
      const greeting=i===0?wave:0
      const thinking=i===0?think:0
      const reminder=i===0?remind:0
      shoulder.rotation.z=side*(.16+.018*breath+greeting*(1.86+.12*Math.sin(phase*4.3))+stretch*2.3+reminder*1.4+happy*(i===0?1.7:.55)+thinking*.30)
      shoulder.rotation.x=-.35*sit-.95*thinking-.10*listen
      shoulder.position.z=.12*thinking
      elbow.rotation.z=side*(.10+greeting*.52+stretch*.1+reminder*.65)-side*thinking*.10
      elbow.rotation.x=-.25-.75*sit-1.3*thinking
      wrist.rotation.y=greeting*.25*Math.sin(phase*4.3-.35)
      wrist.rotation.z=greeting*.18*Math.sin(phase*4.3-.65)+side*.08*stretch
    })
    const autoBlink=!still&&phase%5.6<.16?Math.sin((phase%5.6)/.16*Math.PI):0
    const closed=Math.max(blink,autoBlink,doze*.94)
    const openness=Math.max(.045,1-closed*.97)
    rig.eyes.forEach((eye)=>{
      eye.scale.y=openness
      eye.position.z=.544
      eye.rotation.z=-.18-.06*happy
    })
    rig.mouth.scale.y=1+speak*(.65+.55*Math.sin(phase*13))+happy*.2
    rig.root.rotation.y=-.24+lookX*.04
    return {sit,wave,stretch,doze,think,listen,speak,remind,happy,blink,lookX,lookY,time,hipsY:rig.pelvis.position.y,hip,knee}
  }
  return {update}
}

