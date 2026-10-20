import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { RefObject } from 'react'
import { ACESFilmicToneMapping, SRGBColorSpace } from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
import { PMREMGenerator } from 'three'
import { createPengxiaozhi } from './pengxiaozhiModel'
import { createRobotAnimator } from './pengxiaozhiAnimation'
import type { LookTarget, RobotAction } from './pengxiaozhiAnimation'

type Props = { action: RobotAction; quiet: boolean; paused: boolean; look: RefObject<LookTarget>; onFailure: () => void; onReady: () => void }
function RobotScene({action,quiet,paused,look}: Props) {
  const rig=useMemo(()=>createPengxiaozhi(),[])
  const animator=useMemo(()=>createRobotAnimator(rig),[rig])
  const {invalidate,gl,scene}=useThree()
  useEffect(()=>{
    const generator=new PMREMGenerator(gl)
    const room=new RoomEnvironment()
    const target=generator.fromScene(room,.04)
    scene.environment=target.texture
    scene.environmentIntensity=.8
    generator.dispose();room.dispose()
    return ()=>{scene.environment=null;target.dispose()}
  },[gl,scene])
  useEffect(()=>()=>rig.dispose(),[rig])
  useEffect(()=>{
    if(quiet) for(let i=0;i<180;i++) animator.update('idle',1/60,undefined,true)
    invalidate()
    if(quiet||paused) return
    // Vsync keeps the small independent viewport smooth; paused/quiet views render once.
    let frame=0
    const render=()=>{invalidate();frame=window.requestAnimationFrame(render)}
    frame=window.requestAnimationFrame(render)
    return ()=>window.cancelAnimationFrame(frame)
  },[quiet,paused,action,animator,invalidate])
  useFrame((_,delta)=>{
    if(!quiet&&!paused) animator.update(action,delta,look.current)
  })
  return <>
    <ambientLight intensity={.25}/>
    <hemisphereLight args={['#fff9ed','#5a7565',.65]}/>
    <directionalLight castShadow position={[-3,5,5]} intensity={2.2} color="#fff3df" shadow-mapSize-width={1024} shadow-mapSize-height={1024} shadow-camera-left={-2.5} shadow-camera-right={2.5} shadow-camera-top={4} shadow-camera-bottom={-1} shadow-camera-near={.5} shadow-camera-far={15} shadow-bias={-.0002} shadow-normalBias={.012}/>
    <directionalLight position={[4,2,2]} intensity={.65} color="#d8fff1"/>
    <directionalLight position={[1,4,-3]} intensity={1.1} color="#ffffff"/>
    <primitive object={rig.root} dispose={null}/>
  </>
}
export default function Mascot3DView(props:Props) {
  const [canvas,setCanvas]=useState<HTMLCanvasElement|null>(null)
  const failure=props.onFailure
  const lost=useCallback((event:Event)=>{event.preventDefault();failure()},[failure])
  useEffect(()=>{
    if(!canvas)return
    canvas.addEventListener('webglcontextlost',lost)
    return ()=>canvas.removeEventListener('webglcontextlost',lost)
  },[canvas,lost])
  return <Canvas shadows orthographic camera={{position:[.2,2.45,7],zoom:43,near:.1,far:30}} dpr={[1,1.75]} frameloop="demand"
    gl={{alpha:true,antialias:true,powerPreference:'low-power'}} style={{pointerEvents:'none'}} tabIndex={-1} aria-hidden="true"
    onCreated={({gl,camera})=>{
    gl.setClearColor(0x000000,0);gl.toneMapping=ACESFilmicToneMapping;gl.toneMappingExposure=.95;gl.outputColorSpace=SRGBColorSpace
      camera.lookAt(0,1.4,0)
      gl.domElement.addEventListener('webglcontextlost',lost)
      setCanvas(gl.domElement)
      props.onReady()
    }}>
    <FitCamera/>
    <RobotScene {...props}/>
  </Canvas>
}
function FitCamera() {
  const {camera,size,invalidate}=useThree()
  useEffect(()=>{
    if('zoom' in camera) camera.zoom=size.height/3.05
    camera.updateProjectionMatrix();invalidate()
  },[camera,size.height,invalidate])
  return null
}

