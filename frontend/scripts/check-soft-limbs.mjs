import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { Vector3 } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { createPengxiaozhi } from '../src/features/assistant3d/pengxiaozhiModel.ts'
import { createRobotAnimator } from '../src/features/assistant3d/pengxiaozhiAnimation.ts'

const rig=createPengxiaozhi(),anim=createRobotAnimator(rig),checks=[]
const check=(name,fn)=>{fn();checks.push(name);console.log('PASS',name)}
check('four continuous weighted limbs replace segmented shells',()=>{
  assert.equal(rig.skinnedLimbs.length,4)
  for(const mesh of rig.skinnedLimbs){
    assert(mesh.isSkinnedMesh)
    const weights=mesh.geometry.getAttribute('skinWeight')
    for(let i=0;i<weights.count;i++)assert(Math.abs(weights.getX(i)+weights.getY(i)-1)<1e-6)
  }
})
const tips=[rig.arms[0].wrist,rig.arms[1].wrist,rig.legs[0].ankle,rig.legs[1].ankle]
let maxAttachmentError=0
for(const action of ['idle','wave','sitting','thinking','stretch','idle']){
  for(let f=0;f<90;f++){
    anim.update(action,1/60)
    rig.root.updateMatrixWorld(true)
    rig.skinnedLimbs.forEach((mesh,i)=>{
      mesh.skeleton.update()
      const positions=mesh.geometry.getAttribute('position')
      const tip=new Vector3().fromBufferAttribute(positions,positions.count-1)
      mesh.applyBoneTransform(positions.count-1,tip)
      mesh.localToWorld(tip)
      const distance=tip.distanceTo(tips[i].getWorldPosition(new Vector3()))
      maxAttachmentError=Math.max(maxAttachmentError,distance)
      assert(tip.toArray().every(Number.isFinite))
    })
  }
}
check('skin remains attached to hands and boots throughout bending',()=>assert(maxAttachmentError<.0001,maxAttachmentError))
const bytes=await readFile(new URL('../public/assistant/pengxiaozhi-rigged.glb',import.meta.url))
const model=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')
let skins=0;model.scene.traverse(mesh=>{if(mesh.isSkinnedMesh)skins++})
check('exported GLB preserves four actual skinned limbs',()=>assert.equal(skins,4))
rig.dispose()
await writeFile(new URL('../../.run/mascot-limbs/skin-results.json',import.meta.url),JSON.stringify({passed:checks.length,checks,maxAttachmentError},null,2))
