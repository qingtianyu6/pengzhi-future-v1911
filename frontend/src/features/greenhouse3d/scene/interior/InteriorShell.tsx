import { useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'

const L=32, WALL=3.55, RISE=2.35, BAY=6

function roofGeometry(centerZ:number){
  const seg=64, verts:number[]=[], idx:number[]=[]
  for(const x of [-L/2,L/2]) for(let i=0;i<=seg;i++){
    const t=Math.PI-Math.PI*i/seg
    verts.push(x,WALL+RISE*Math.sin(t),centerZ+(BAY/2)*Math.cos(t))
  }
  for(let i=0;i<seg;i++){const a=i,b=i+1,c=seg+1+i,d=c+1;idx.push(a,c,b,b,c,d)}
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));g.setIndex(idx);g.computeVertexNormals();return g
}
function archCap(centerZ:number,x:number){
  const seg=32, verts:number[]=[x,WALL,centerZ], idx:number[]=[]
  for(let i=0;i<=seg;i++){const t=Math.PI-Math.PI*i/seg;verts.push(x,WALL+RISE*Math.sin(t),centerZ+(BAY/2)*Math.cos(t))}
  for(let i=0;i<seg;i++) idx.push(0,i+1,i+2)
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));g.setIndex(idx);g.computeVertexNormals();return g
}
function CylinderBetween({a,b,r,color,shadow=false}:{a:[number,number,number],b:[number,number,number],r:number,color:string,shadow?:boolean}){
  const {mid,q,len}=useMemo(()=>{const A=new THREE.Vector3(...a),B=new THREE.Vector3(...b),v=B.clone().sub(A),len=v.length(),mid=A.clone().add(B).multiplyScalar(.5),q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize());return{mid,q,len}},[a,b])
  return <mesh position={mid} quaternion={q} castShadow={shadow}><cylinderGeometry args={[r,r,len,8]}/><meshStandardMaterial color={color} metalness={.82} roughness={.26}/></mesh>
}
function ArchRibs({ xs }: { xs: number[] }) {
  const ref = useRef<THREE.InstancedMesh>(null)
  const matrices = useMemo(() => {
    const up = new THREE.Vector3(0, 1, 0)
    const result: THREE.Matrix4[] = []
    for (const x of xs) for (const cz of [-6, 0, 6]) for (let k = 0; k < 24; k++) {
      const t1 = Math.PI - Math.PI * k / 24
      const t2 = Math.PI - Math.PI * (k + 1) / 24
      const a = new THREE.Vector3(x, WALL + RISE * Math.sin(t1), cz + (BAY / 2) * Math.cos(t1))
      const b = new THREE.Vector3(x, WALL + RISE * Math.sin(t2), cz + (BAY / 2) * Math.cos(t2))
      const direction = b.clone().sub(a)
      result.push(new THREE.Matrix4().compose(
        a.add(b).multiplyScalar(0.5),
        new THREE.Quaternion().setFromUnitVectors(up, direction.clone().normalize()),
        new THREE.Vector3(1, direction.length(), 1),
      ))
    }
    return result
  }, [xs])
  useLayoutEffect(() => {
    if (!ref.current) return
    matrices.forEach((matrix, index) => ref.current?.setMatrixAt(index, matrix))
    ref.current.instanceMatrix.needsUpdate = true
    ref.current.computeBoundingSphere()
  }, [matrices])
  return <instancedMesh ref={ref} args={[undefined, undefined, matrices.length]}>
    <cylinderGeometry args={[0.029, 0.029, 1, 8]} />
    <meshStandardMaterial color="#bac6ca" metalness={0.82} roughness={0.26} />
  </instancedMesh>
}
const Film=()=> <meshPhysicalMaterial side={THREE.DoubleSide} color="#e3ece5" transmission={.2} thickness={.07} ior={1.45} roughness={.38} metalness={0}/>
export default function InteriorShell({inspection=false,aisleWidth=1.4}:{inspection?:boolean;aisleWidth?:number}){
  const roofs=useMemo(()=>[-6,0,6].map(roofGeometry),[]), xs=useMemo(()=>Array.from({length:14},(_,i)=>-16+i*(32/13)),[]), frontCaps=useMemo(()=>[-6,0,6].map(c=>archCap(c,-15.985)),[]), rearCaps=useMemo(()=>[-6,0,6].map(c=>archCap(c,15.985)),[])
  return <group>
    <mesh receiveShadow position={[0,-.09,0]}><boxGeometry args={[32,.12,18]}/><meshStandardMaterial color="#68736d" roughness={.95}/></mesh>
    <mesh receiveShadow position={[0,.015,0]}><boxGeometry args={[30.6,.055,aisleWidth]}/><meshStandardMaterial color="#aebbb2" roughness={.88}/></mesh>
    {Array.from({length:15},(_,index)=><mesh key={`aisle-joint-${index}`} position={[-14.5+index*2.1,.045,0]}><boxGeometry args={[.018,.004,aisleWidth]}/><meshStandardMaterial color="#81938b" roughness={.94}/></mesh>)}
    {[-1,1].map(side=><mesh key={`aisle-line-${side}`} position={[0,.048,side*(aisleWidth/2-.12)]}><boxGeometry args={[30.2,.004,.025]}/><meshStandardMaterial color="#c8ad6b" roughness={.8}/></mesh>)}
    <mesh receiveShadow position={[0,.005,-aisleWidth/2-.10]}><boxGeometry args={[30.6,.035,.08]}/><meshStandardMaterial color="#747c7b" roughness={.82}/></mesh>
    <mesh receiveShadow position={[0,.005,aisleWidth/2+.10]}><boxGeometry args={[30.6,.035,.08]}/><meshStandardMaterial color="#747c7b" roughness={.82}/></mesh>
    {!inspection && <>
      {roofs.map((g,i)=><mesh key={i} geometry={g}><Film/></mesh>)}
      <mesh position={[0,WALL/2,-8.99]}><boxGeometry args={[32,WALL,.035]}/><Film/></mesh><mesh position={[0,WALL/2,8.99]}><boxGeometry args={[32,WALL,.035]}/><Film/></mesh>
      {[-8.94,8.94].map((z)=><group key={`vent-${z}`}>
        <mesh position={[0,2.83,z]}><boxGeometry args={[31.4,.48,.045]}/><meshStandardMaterial color="#87a4a0" metalness={.22} roughness={.58}/></mesh>
        {Array.from({length:8},(_,index)=><mesh key={index} position={[-13.7+index*3.9,2.83,z+(z<0?.035:-.035)]}><boxGeometry args={[.055,.52,.055]}/><meshStandardMaterial color="#718b89" metalness={.5} roughness={.42}/></mesh>)}
        <mesh position={[0,2.98,z+(z<0?.045:-.045)]}><boxGeometry args={[31.4,.025,.025]}/><meshStandardMaterial color="#d7e3d9" metalness={.32} roughness={.48}/></mesh>
      </group>)}
      {/* front/rear arch caps close the greenhouse and remove tunnel-like bright holes */}
      {frontCaps.map((g,i)=><mesh key={'f'+i} geometry={g}><Film/></mesh>)}{rearCaps.map((g,i)=><mesh key={'r'+i} geometry={g}><Film/></mesh>)}
      {/* front lower wall split around 2.4 m entrance */}
      <mesh position={[-15.985,WALL/2,-5.1]}><boxGeometry args={[.035,WALL,7.8]}/><Film/></mesh>
      <mesh position={[-15.985,WALL/2,5.1]}><boxGeometry args={[.035,WALL,7.8]}/><Film/></mesh>
      <mesh position={[-15.985,3.05,0]}><boxGeometry args={[.035,1.0,2.4]}/><Film/></mesh>
      {/* rear lower wall around continuous cooling-pad opening */}
      <mesh position={[15.985,WALL/2,-6.9]}><boxGeometry args={[.035,WALL,4.2]}/><Film/></mesh><mesh position={[15.985,WALL/2,6.9]}><boxGeometry args={[.035,WALL,4.2]}/><Film/></mesh>
      <mesh position={[15.985,3.05,0]}><boxGeometry args={[.035,1.0,9.6]}/><Film/></mesh>
      {xs.map((x,ix)=>[-9,-3,3,9].map((z,j)=><CylinderBetween key={`c${ix}-${j}`} a={[x,0,z]} b={[x,WALL,z]} r={.043} color="#bac6ca" shadow={ix%3===0}/>))}
      <ArchRibs xs={xs} />
      {[-9,-3,3,9].flatMap((z,j)=>[1.25,2.35,3.5].map((y,k)=><CylinderBetween key={`b${j}-${k}`} a={[-16,y,z]} b={[16,y,z]} r={.021} color="#aebbc0"/>))}
      {/* entrance frame */}
      <CylinderBetween a={[-15.94,0,-1.2]} b={[-15.94,2.65,-1.2]} r={.035} color="#aebbc0"/><CylinderBetween a={[-15.94,0,1.2]} b={[-15.94,2.65,1.2]} r={.035} color="#aebbc0"/><CylinderBetween a={[-15.94,2.65,-1.2]} b={[-15.94,2.65,1.2]} r={.035} color="#aebbc0"/>
      {/* continuous rear cooling pad */}
      <group position={[15.91,1.35,0]}>
        <mesh><boxGeometry args={[.08,2.55,9.55]}/><meshStandardMaterial color="#a59c87" roughness={.88}/></mesh>
        {Array.from({length:20},(_,index)=><mesh key={`pad-slat-${index}`} position={[-.052,0,-4.52+index*.47]}><boxGeometry args={[.012,2.45,.025]}/><meshStandardMaterial color="#817f70" roughness={.9}/></mesh>)}
        {[-4.8,-1.6,1.6,4.8].map(z=><mesh key={z} position={[-.05,0,z]}><boxGeometry args={[.05,2.72,.055]}/><meshStandardMaterial color="#aeb8bc" metalness={.65} roughness={.32}/></mesh>)}
        {[-1.28,1.28].map(y=><mesh key={y} position={[-.05,y,0]}><boxGeometry args={[.05,.055,9.7]}/><meshStandardMaterial color="#aeb8bc" metalness={.65} roughness={.32}/></mesh>)}
      </group>
    </>}
  </group>
}
