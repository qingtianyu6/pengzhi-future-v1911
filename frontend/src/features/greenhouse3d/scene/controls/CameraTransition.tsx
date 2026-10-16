import { useFrame,useThree } from '@react-three/fiber'
import { useRef } from 'react'
import * as THREE from 'three'
import type { ExteriorBounds } from '../exterior/GreenhouseExterior'

export default function CameraTransition({active,bounds,spawn,onDone}:{active:boolean;bounds:ExteriorBounds|null;spawn:[number,number,number];onDone:()=>void}){
 const{camera}=useThree(),t=useRef(0),start=useRef<THREE.Vector3|null>(null),done=useRef(false)
 useFrame((_,dt)=>{
	 if(!active){t.current=0;start.current=null;done.current=false;return}
	 if(!bounds||done.current)return
	 start.current??=camera.position.clone()
	 t.current=Math.min(1,t.current+dt/2.2)
	 const progress=t.current*t.current*(3-2*t.current)
	 const destination=new THREE.Vector3(...spawn)
	 const lookFrom=bounds.center.clone().add(new THREE.Vector3(0,bounds.size.y*.12,0))
	 const lookTo=destination.clone().add(new THREE.Vector3(-8,-.05,0))
	 camera.position.lerpVectors(start.current,destination,progress)
	 camera.lookAt(lookFrom.lerp(lookTo,progress))
	 if(t.current>=1){done.current=true;onDone()}
 })
 return null
}
