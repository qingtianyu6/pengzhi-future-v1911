import { mkdir, writeFile } from 'node:fs/promises'
import * as THREE from 'three'
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js'
import { createPengxiaozhi } from '../src/features/assistant3d/pengxiaozhiModel.ts'
import { createRobotAnimator } from '../src/features/assistant3d/pengxiaozhiAnimation.ts'

// GLTFExporter only needs Blob->ArrayBuffer when no image textures are embedded.
globalThis.FileReader=class {
  result=null
  onloadend=null
  async readAsArrayBuffer(blob){this.result=await blob.arrayBuffer();this.onloadend?.()}
  async readAsDataURL(blob){this.result='data:'+blob.type+';base64,'+Buffer.from(await blob.arrayBuffer()).toString('base64');this.onloadend?.()}
}
const rig=createPengxiaozhi()
const nodes=[rig.root,rig.pelvis,rig.torso,rig.head,...rig.arms.flatMap(a=>[a.shoulder,a.elbow,a.wrist]),...rig.legs.flatMap(l=>[l.hip,l.knee,l.ankle]),...rig.eyes,rig.mouth]
const definitions=[
 ['Idle','idle',3,null],['Wave','wave',2.4,null],['SitDown','sitting',1.8,null],
 ['Sitting','sitting',3,'sitting'],['StandUp','idle',1.8,'sitting'],
 ['Dozing','dozing',3,'sitting'],['Stretch','stretch',3,null],['Thinking','thinking',3,null],
 ['Listening','listening',3,null],['Speaking','speaking',3,null],['Reminder','reminder',2.5,null],['Complete','complete',2.5,null],
]
const clips=definitions.map(([name,action,duration,initial])=>{
 const animator=createRobotAnimator(rig)
 for(let i=0;i<300;i++)animator.update('idle',1/60,undefined,true)
 if(initial)for(let i=0;i<240;i++)animator.update(initial,1/60)
 const times=[],samples=nodes.map(()=>({q:[],p:[],s:[]}))
 for(let i=0;i<=Math.round(duration*30);i++){
  const t=i/30;times.push(t)
  if(i)animator.update(action,1/30)
  nodes.forEach((n,index)=>{samples[index].q.push(...n.quaternion.toArray());samples[index].p.push(...n.position.toArray());samples[index].s.push(...n.scale.toArray())})
 }
 const tracks=[]
 const differs=(a,stride)=>a.some((v,i)=>Math.abs(v-a[i%stride])>.00001)
 nodes.forEach((node,i)=>{
  const sample=samples[i]
  tracks.push(new THREE.QuaternionKeyframeTrack(node.name+'.quaternion',times,sample.q))
  if(node===rig.pelvis||node===rig.torso||differs(sample.p,3))tracks.push(new THREE.VectorKeyframeTrack(node.name+'.position',times,sample.p))
  if(rig.eyes.includes(node)||node===rig.mouth||differs(sample.s,3))tracks.push(new THREE.VectorKeyframeTrack(node.name+'.scale',times,sample.s))
 })
 return new THREE.AnimationClip(name,duration,tracks)
})
const reset=createRobotAnimator(rig)
for(let i=0;i<300;i++)reset.update('idle',1/60,undefined,true)
const folder=new URL('../public/assistant/',import.meta.url);await mkdir(folder,{recursive:true})
const binary=await new GLTFExporter().parseAsync(rig.root,{binary:true,animations:clips})
await writeFile(new URL('pengxiaozhi-rigged.glb',folder),Buffer.from(binary))
let meshes=0,triangles=0,bones=0,skinnedMeshes=0
rig.root.traverse(item=>{
 if(item.isMesh){meshes++;triangles+=(item.geometry.index?.count??item.geometry.attributes.position.count)/3}
 if(item.isBone)bones++
 if(item.isSkinnedMesh)skinnedMeshes++
})
const report={name:'棚小智',type:'Original rigged character with continuous skinned limbs',meshes,skinnedMeshes,triangles,bones,bytes:binary.byteLength,animations:clips.map(c=>({name:c.name,duration:c.duration,tracks:c.tracks.length})),source:'src/features/assistant3d/pengxiaozhiModel.ts',runtimeAnimation:'src/features/assistant3d/pengxiaozhiAnimation.ts',notes:'GLB animations are editable offline samples of the live blended joint controller. The app uses that same model source for continuous mouse tracking and interruptible movements.'}
await writeFile(new URL('pengxiaozhi-model.json',folder),JSON.stringify(report,null,2))
rig.dispose()
console.log(JSON.stringify(report))

