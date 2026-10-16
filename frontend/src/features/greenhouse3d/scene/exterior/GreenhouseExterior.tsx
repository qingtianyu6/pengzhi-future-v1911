import { useGLTF } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useEffect,useMemo,useRef } from 'react'
import * as THREE from 'three'

export type ExteriorBounds = { box: THREE.Box3; size: THREE.Vector3; center: THREE.Vector3 }

const colors:Record<string,string>={
  MAT_PC_Panel:'#dde8e7',MAT_PC_Panel_Cool:'#d8e7ea',MAT_PC_Warm:'#ecebe2',MAT_Door_Glass:'#cae2e6',
  MAT_Galvanized_Main:'#b5c2c7',MAT_Galvanized_Mid:'#c0cbcf',MAT_Galvanized_Light:'#d0d8db',MAT_Connector:'#aab7bc',
  MAT_Bottom_Skirt:'#59676d',MAT_Fan_Frame:'#aeb9be',MAT_Fan_Dark:'#4a565c',MAT_Fan_Shutter:'#bdc6c9',
  MAT_Foundation:'#d2d5d3',MAT_Cabinet:'#d6dcdd',MAT_Motor:'#78888f',MAT_Handle:'#68757a',MAT_RubberSeal:'#48555a'
}

export default function GreenhouseExterior({doorOpen,onClick,onBounds}:{doorOpen:boolean;onClick:()=>void;onBounds:(bounds:ExteriorBounds)=>void}){
  const{scene}=useGLTF('/3d-assets/greenhouse/greenhouse_shell_v9_1.glb')
  const clone=useMemo(()=>scene.clone(true),[scene])
  const p=useRef(0)
  const left=useMemo(()=>clone.getObjectByName('Entrance_System/Entrance_Door_Left')??clone.getObjectByName('Entrance_Door_Left'),[clone])
  const right=useMemo(()=>clone.getObjectByName('Entrance_System/Entrance_Door_Right')??clone.getObjectByName('Entrance_Door_Right'),[clone])
  const lp=useMemo(()=>left?.position.clone(),[left]),rp=useMemo(()=>right?.position.clone(),[right])

  useEffect(()=>{
    clone.updateWorldMatrix(true,true)
    const rawBox=new THREE.Box3().setFromObject(clone)
    const visualBox=new THREE.Box3()
    clone.traverse(object=>{
      if((object as THREE.Mesh).isMesh&&!object.name.startsWith('Interaction_Anchors'))visualBox.expandByObject(object)
    })
    visualBox.applyMatrix4(new THREE.Matrix4().makeRotationX(-Math.PI/2))
    const size=visualBox.getSize(new THREE.Vector3())
    const center=visualBox.getCenter(new THREE.Vector3())
    console.info('[GreenhouseExterior] GLB bounds',{
      min:rawBox.min.toArray(),max:rawBox.max.toArray(),
      size:rawBox.getSize(new THREE.Vector3()).toArray(),center:rawBox.getCenter(new THREE.Vector3()).toArray(),
      sourceAxes:{xLength:size.x,yHeight:size.y,zWidth:size.z},
      fitted:{min:visualBox.min.toArray(),max:visualBox.max.toArray(),size:size.toArray(),center:center.toArray()},
      transform:{position:[0,0,0],rotation:[-Math.PI/2,0,0],scale:[1,1,1]}
    })
    onBounds({box:visualBox,size,center})
  },[clone,onBounds])

  useEffect(()=>{
    const cache=new Map<THREE.Material,THREE.Material>()
    clone.traverse(o=>{
      if(!(o as THREE.Mesh).isMesh)return
      const mesh=o as THREE.Mesh
      const source=mesh.material as THREE.MeshStandardMaterial
      let m=cache.get(source) as THREE.MeshStandardMaterial|undefined
      if(!m){
        m=source.clone() as THREE.MeshStandardMaterial
        const name=source.name||''
        if(colors[name])m.color.set(colors[name])
        if(name.includes('Galvanized')){m.metalness=.84;m.roughness=.26}
        if(name==='MAT_Bottom_Skirt'){m.roughness=.48;m.metalness=.18}
        if(name.includes('Fan_')){m.roughness=.34;m.metalness=name==='MAT_Fan_Dark'?.38:.72}
        if(name.includes('PC_')||name==='MAT_PC_Panel'){
          const pm=m as THREE.MeshPhysicalMaterial
          pm.metalness=0;pm.roughness=.31;pm.transparent=false;pm.opacity=1
          if('transmission'in pm){pm.transmission=.14;pm.ior=1.45;pm.thickness=.07;pm.clearcoat=.14;pm.clearcoatRoughness=.33}
        }
        if(name==='MAT_Door_Glass'){m.transparent=true;m.opacity=.88;m.roughness=.18}
        if(name==='MAT_Foundation'){m.metalness=0;m.roughness=.78}
        cache.set(source,m)
      }
      mesh.material=m
      mesh.castShadow=!o.name.includes('PanelClamp')&&!o.name.includes('ProtectionGrid')
      mesh.receiveShadow=true
    })
  },[clone])

  useFrame((_,dt)=>{
    p.current=THREE.MathUtils.damp(p.current,doorOpen?1:0,4.6,dt)
    const smooth=p.current*p.current*(3-2*p.current)
    if(left&&lp)left.position.z=lp.z-.75*smooth
    if(right&&rp)right.position.z=rp.z+.75*smooth
  })
  return <group rotation={[-Math.PI/2,0,0]} userData={{g3dExterior:true}} onClick={e=>{e.stopPropagation();onClick()}}><primitive object={clone}/></group>
}
useGLTF.preload('/3d-assets/greenhouse/greenhouse_shell_v9_1.glb')
