import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AgriculturalAgentMascot } from './AgriculturalAgentMascot'
import type { MascotState } from './AgriculturalAgentMascot'
import type { CompanionMotion } from '../hooks/useMascotCompanion'
import type { LookTarget } from '../features/assistant3d/pengxiaozhiAnimation'

const Mascot3DView=lazy(()=>import('../features/assistant3d/Mascot3DView'))

class ViewportBoundary extends Component<{children:ReactNode;fallback:ReactNode;onFailure:()=>void},{failed:boolean}> {
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  componentDidCatch(){this.props.onFailure()}
  render(){return this.state.failed?this.props.fallback:this.props.children}
}
export function LiveAgriculturalMascot({state='idle',motion='idle',quiet=false,paused=false,onRendererChange}:{
  state?:MascotState;motion?:CompanionMotion;quiet?:boolean;paused?:boolean;onRendererChange?:(fallback:boolean)=>void
}) {
  const host=useRef<HTMLSpanElement>(null)
  const look=useRef<LookTarget>({x:0,y:0,active:false})
  const [failed,setFailed]=useState(false)
  const [initialized,setInitialized]=useState(false)
  const failure=useCallback(()=>{setFailed(true);onRendererChange?.(true)},[onRendererChange])
  const ready=useCallback(()=>{setInitialized(true);onRendererChange?.(false)},[onRendererChange])
  useEffect(()=>{
    if(quiet||paused||failed) return
    const move=(event:PointerEvent)=>{
      if(event.pointerType==='touch') return
      const rect=host.current?.getBoundingClientRect()
      if(!rect)return
      look.current={x:(event.clientX-(rect.left+rect.width/2))/Math.max(220,innerWidth*.5),y:(event.clientY-(rect.top+rect.height*.35))/Math.max(180,innerHeight*.5),active:true}
    }
    const reset=()=>{look.current={x:0,y:0,active:false}}
    window.addEventListener('pointermove',move,{passive:true});window.addEventListener('blur',reset);document.addEventListener('pointerleave',reset)
    return ()=>{window.removeEventListener('pointermove',move);window.removeEventListener('blur',reset);document.removeEventListener('pointerleave',reset);reset()}
  },[quiet,paused,failed])
  const fallback=<AgriculturalAgentMascot state={state} showStateBadge={false}/>
  const action=state==='idle'?motion:state
  return <span ref={host} className={`mascot-three-view${failed?' is-fallback':''}`} data-renderer={failed?'static':'three'} data-ready={initialized&&!failed} data-action={action} aria-hidden="true">
    {failed?fallback:<ViewportBoundary fallback={fallback} onFailure={failure}>
      <Suspense fallback={fallback}><Mascot3DView action={action} quiet={quiet} paused={paused} look={look} onFailure={failure} onReady={ready}/></Suspense>
    </ViewportBoundary>}
  </span>
}

