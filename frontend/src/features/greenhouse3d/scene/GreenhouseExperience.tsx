import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useThree } from '@react-three/fiber'
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import type { GreenhouseInteriorConfig } from './config/types'
import { generateInteriorLayout } from './generation/layoutEngine'
import GreenhouseExterior, { type ExteriorBounds } from './exterior/GreenhouseExterior'
import GreenhouseInterior from './interior/GreenhouseInterior'
import CameraTransition from './controls/CameraTransition'
import FirstPersonController from './controls/FirstPersonController'
import type { MovementInput, ViewPoint, ViewStop, WalkPosition } from './controls/FirstPersonController'
import PreviewCamera from './controls/PreviewCamera'
import { bedMock } from './interaction/BedInteraction'
import { deviceMock } from './interaction/DeviceInteraction'
import ScenePicker from './interaction/ScenePicker'
import type { GrowthStage } from '../../../types/cropBatch'

export type ExperienceMode='outside'|'confirm'|'entering'|'inside'
function ResponsiveCameraFov(){
 const camera=useThree(state=>state.camera),size=useThree(state=>state.size)
 useEffect(()=>{
   if(!(camera instanceof THREE.PerspectiveCamera))return
   camera.fov=size.width<640?72:54
   camera.updateProjectionMatrix()
 },[camera,size.width])
 return null
}
function ExteriorCameraRig({bounds,mode,resetToken,enabled}:{bounds:ExteriorBounds|null;mode:ExperienceMode;resetToken:string;enabled:boolean}){
 const camera=useThree(state=>state.camera),size=useThree(state=>state.size),controls=useRef<OrbitControlsImpl>(null)
 const fit=useCallback(()=>{
   if(!bounds||!(camera instanceof THREE.PerspectiveCamera)||!controls.current)return
   camera.near=.1
   camera.far=500
   camera.updateProjectionMatrix()
   const target=bounds.center.clone().add(new THREE.Vector3(0,bounds.size.y*.12,0))
   const elevation=THREE.MathUtils.degToRad(22)
   const direction=new THREE.Vector3(Math.cos(elevation)/Math.sqrt(2),Math.sin(elevation),Math.cos(elevation)/Math.sqrt(2))
   const forward=direction.clone().negate()
   const right=forward.clone().cross(new THREE.Vector3(0,1,0)).normalize()
   const up=right.clone().cross(forward).normalize()
   const projectedWidth=Math.abs(right.x)*bounds.size.x+Math.abs(right.y)*bounds.size.y+Math.abs(right.z)*bounds.size.z
   const projectedHeight=Math.abs(up.x)*bounds.size.x+Math.abs(up.y)*bounds.size.y+Math.abs(up.z)*bounds.size.z
   const verticalHalfFov=THREE.MathUtils.degToRad(camera.fov/2)
   const horizontalHalfFov=Math.atan(Math.tan(verticalHalfFov)*camera.aspect)
   const distance=Math.max(projectedWidth/(2*Math.tan(horizontalHalfFov)),projectedHeight/(2*Math.tan(verticalHalfFov)))*1.32
   controls.current.target.copy(target)
   controls.current.minDistance=Math.max(2,bounds.size.y*.75)
   controls.current.maxDistance=distance*3
   camera.position.copy(target).addScaledVector(direction,distance)
   controls.current.update()
   console.info('[GreenhouseExterior] exterior camera fit',{
     position:camera.position.toArray(),target:controls.current.target.toArray(),distance,
     aspect:size.width/size.height,near:camera.near,far:camera.far
   })
 },[bounds,camera,size.width,size.height])
 useEffect(()=>{if(enabled&&mode==='outside')fit()},[enabled,fit,mode,resetToken])
 return <OrbitControls ref={controls} enabled={enabled&&mode==='outside'} enableDamping dampingFactor={.08} minPolarAngle={THREE.MathUtils.degToRad(8)} maxPolarAngle={THREE.MathUtils.degToRad(82)} />
}

export default function GreenhouseExperience({config,mode,onMode,onSelection,lightsOn,growthStage,movement,position,navigation}:{config:GreenhouseInteriorConfig;mode:ExperienceMode;onMode:(m:ExperienceMode)=>void;onSelection:(v:Record<string,unknown>)=>void;lightsOn:boolean;growthStage:GrowthStage|null;movement:RefObject<MovementInput>;position:RefObject<WalkPosition>;navigation:RefObject<ViewStop|null>}){
 const params=useMemo(()=>new URLSearchParams(window.location.search),[]),preview=params.get('preview')||'',previewMode=Boolean(preview),inspection=preview==='top'
 const layout=useMemo(()=>generateInteriorLayout(config),[config])
 const [bounds,setBounds]=useState<ExteriorBounds|null>(null)
 const spawn=useMemo<[number,number,number]>(()=>{
   const [x,y,z]=layout.anchors.Camera_Inside_Start
   return [-x,y,-z]
 },[layout])
 const interiorColliders=useMemo(()=>layout.colliders.map(collider=>({
   ...collider,
   min:[-collider.max[0],collider.min[1],-collider.max[2]] as [number,number,number],
   max:[-collider.min[0],collider.max[1],-collider.min[2]] as [number,number,number],
 })),[layout.colliders])
 const viewPoints=useMemo<Record<ViewStop,ViewPoint>>(()=>{
   const entrance:ViewPoint={position:spawn,target:[0,1.6,0]}
   const points=Object.fromEntries(layout.zones.map(zone=>[zone.id,{
     position:[-zone.anchor[0],spawn[1],0],
     target:[-zone.anchor[0],1.45,-zone.anchor[2]],
   }])) as Partial<Record<ViewStop,ViewPoint>>
   return {entrance,A:points.A??entrance,B:points.B??entrance,C:points.C??entrance,D:points.D??entrance}
 },[layout.zones,spawn])
 const outside=mode==='outside'||mode==='confirm'||mode==='entering'
 const selectBed=(id:string)=>{const b=layout.beds.find(x=>x.id===id);if(b)onSelection(bedMock(id,b.crop))}
 const selectDevice=(id:string)=>onSelection(deviceMock(id))
 return <div className="experience"><Canvas shadows camera={{position:[0,0,0],fov:54,near:.1,far:500}} dpr={[1,1.7]} onCreated={({gl})=>{
   gl.toneMapping=THREE.ACESFilmicToneMapping
   gl.toneMappingExposure=lightsOn?.96:1.02
   gl.outputColorSpace=THREE.SRGBColorSpace
   gl.shadowMap.type=THREE.PCFSoftShadowMap
 }}>
   <ResponsiveCameraFov/>
   <color attach="background" args={[lightsOn?'#253c36':outside?'#edf1e7':'#e6eee5']}/>
   {!inspection&&<fog attach="fog" args={[lightsOn?'#253c36':outside?'#edf1e7':'#e6eee5',34,76]}/>}
   <ambientLight intensity={lightsOn?.26:outside?.52:.60}/>
   <hemisphereLight args={[lightsOn?'#536979':'#fff9ec',lightsOn?'#1e272c':'#86967b',lightsOn?.32:outside?.84:1.0]}/>
   <directionalLight castShadow={!inspection} position={[8,16,-7]} intensity={lightsOn?.14:outside?.92:1.0} color={lightsOn?'#9aa9b2':'#fff4e8'} shadow-mapSize-width={2048} shadow-mapSize-height={2048}/>
   <directionalLight position={[-10,10,8]} intensity={lightsOn?.08:outside?.36:.3} color="#c8e5f4"/>
   {outside&&<mesh receiveShadow position={[0,-.12,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[54,42]}/><meshStandardMaterial color="#d8e1ca" roughness={.85}/></mesh>}
   {mode!=='inside'&&<GreenhouseExterior doorOpen={mode==='entering'} onClick={()=>mode==='outside'&&onMode('confirm')} onBounds={setBounds}/>} 
  {(mode==='entering'||mode==='inside')&&layout.valid&&<group rotation={[0,Math.PI,0]}><GreenhouseInterior config={config} layout={layout} lightsOn={lightsOn} growthStage={growthStage} inspection={inspection} onBed={selectBed} onDevice={selectDevice}/></group>} 
   <ScenePicker onBed={selectBed} onDevice={selectDevice} onExterior={()=>{if(mode==='outside')onMode('confirm')}}/>
   <ExteriorCameraRig bounds={bounds} mode={mode} resetToken={config.greenhouseId} enabled={!previewMode}/>
   <CameraTransition active={mode==='entering'} bounds={bounds} spawn={spawn} onDone={()=>onMode('inside')}/>
   <FirstPersonController enabled={mode==='inside'&&!previewMode} colliders={interiorColliders} spawn={spawn} movement={movement} position={position} navigation={navigation} viewPoints={viewPoints}/>
   {previewMode&&<PreviewCamera preset={preview}/>} 
 </Canvas>{!layout.valid&&<div className="validation-card">{layout.errors.join('；')}</div>}</div>
}
