import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'
import { createPengxiaozhi } from '../src/features/assistant3d/pengxiaozhiModel.ts'
import { createRobotAnimator } from '../src/features/assistant3d/pengxiaozhiAnimation.ts'

const rig=createPengxiaozhi(),anim=createRobotAnimator(rig),checks=[]
const check=(name,fn)=>{fn();checks.push(name);console.log('PASS',name)}
let previous,pose
for(let i=0;i<18;i++){previous=pose;pose=anim.update('sitting',1/60)}
const interrupted=anim.update('wave',1/60)
check('mid-sit interruption keeps forward momentum instead of reversing instantly',()=>{
  assert(pose.sit>previous.sit)
  assert(interrupted.sit>pose.sit)
  assert(interrupted.sit-pose.sit<.05)
})
for(let i=0;i<180;i++)pose=anim.update('wave',1/60)
check('interrupted sit finishes standing and greeting',()=>assert(pose.sit<.001&&pose.wave>.99))
let maxStep=0
const joints=[rig.pelvis,rig.torso,rig.head,...rig.arms.flatMap(a=>[a.shoulder,a.elbow,a.wrist]),...rig.legs.flatMap(l=>[l.hip,l.knee,l.ankle])]
const actions=['wave','sitting','thinking','stretch','listening','speaking','complete','dozing','idle']
for(let i=0;i<720;i++){
  const before=joints.map(j=>j.quaternion.clone())
  anim.update(actions[Math.floor(i/12)%actions.length],1/60,{x:Math.sin(i*.05),y:Math.cos(i*.04),active:true})
  joints.forEach((j,k)=>{maxStep=Math.max(maxStep,before[k].angleTo(j.quaternion))})
}
check('rapid interruptions stay within a bounded per-frame joint rotation',()=>assert(maxStep<.30,maxStep))
let triangles=0,meshes=0,gloves=0
rig.root.traverse(item=>{
  if(!item.isMesh)return
  meshes++;triangles+=(item.geometry.index?.count??item.geometry.attributes.position.count)/3
  const pos=item.geometry.getAttribute('position')
  for(let i=0;i<pos.array.length;i++)assert(Number.isFinite(pos.array[i]),item.name)
  if(['UpperArmShell','ForearmShell','ThighShell','ShinShell'].includes(item.name)){
    const normals=item.geometry.getAttribute('normal')
    let outward=0,inward=0
    for(let i=0;i<pos.count;i++){
      const dot=pos.getX(i)*normals.getX(i)+pos.getZ(i)*normals.getZ(i)
      if(dot>.02)outward++
      if(dot<-.02)inward++
    }
    assert(outward>inward*5,'limb shell must face outward, not disappear through back-face culling')
  }
  if(item.name==='SculptedGlove'){
    gloves++
    item.geometry.computeBoundingBox()
    assert(item.geometry.boundingBox.max.z-item.geometry.boundingBox.min.z>.12,'glove must have actual volume')
    const copy=item.geometry.clone();copy.deleteAttribute('normal')
    const welded=mergeVertices(copy,1e-5),indices=welded.index.array
    const roots=Array.from({length:welded.attributes.position.count},(_,i)=>i)
    const find=i=>{while(roots[i]!==i){roots[i]=roots[roots[i]];i=roots[i]}return i}
    for(let i=0;i<indices.length;i+=3){roots[find(indices[i+1])]=find(indices[i]);roots[find(indices[i+2])]=find(indices[i])}
    assert.equal(new Set(roots.map((_,i)=>find(i))).size,1,'glove fingers must connect to palm')
    copy.dispose();welded.dispose()
  }
})
check('both gloves have real volume and generated geometry stays finite',()=>assert.equal(gloves,2))
check('small viewport model stays within geometry budget',()=>assert(triangles<140000&&meshes<=65))
rig.dispose()
await writeFile(new URL('../../.run/mascot-refinement/refinement-results.json',import.meta.url),JSON.stringify({passed:checks.length,checks,maxJointStepRadians:maxStep,triangles,meshes},null,2))
