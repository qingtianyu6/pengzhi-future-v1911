import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { AnimationMixer, Vector3 } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { createPengxiaozhi } from '../src/features/assistant3d/pengxiaozhiModel.ts'
import { createRobotAnimator } from '../src/features/assistant3d/pengxiaozhiAnimation.ts'
const results=[]
const check=(name,fn)=>{fn();results.push({case:name,passed:true});console.log('PASS',name)}
const rig=createPengxiaozhi(),anim=createRobotAnimator(rig),look={x:0,y:0,active:false}
check('sixteen_editable_mechanical_joints',()=>{let n=0;rig.root.traverse(o=>{if(o.isBone)n++});assert.equal(n,16)})
let previous=anim.update('idle',1/60,look,true),intermediate=false,maxHipStep=0,maxFloorError=0
for(let i=0;i<150;i++){
 const pose=anim.update('sitting',1/60,look)
 maxHipStep=Math.max(maxHipStep,Math.abs(pose.hip-previous.hip))
 if(pose.sit>.1&&pose.sit<.9)intermediate=true
 rig.root.updateMatrixWorld(true)
 for(const leg of rig.legs){const pos=leg.ankle.getWorldPosition(new Vector3());maxFloorError=Math.max(maxFloorError,Math.abs(pos.y-.28))}
 previous=pose
}
check('sitting_has_intermediate_joint_poses',()=>{assert(intermediate);assert(previous.sit>.99);assert(maxHipStep<.11)})
check('feet_stay_on_floor_through_transition',()=>assert(maxFloorError<.016,maxFloorError))
check('seated_body_reaches_floor',()=>assert(Math.abs(previous.hipsY-.32)<.008))
const before=previous
const interruption=anim.update('wave',1/60,look)
check('waking_does_not_teleport_to_standing_pose',()=>{assert(interruption.sit>.9);assert(interruption.sit<before.sit);assert(Math.abs(interruption.hip-before.hip)<.11)})
for(let i=0;i<180;i++)previous=anim.update('wave',1/60,{x:-1,y:-.5,active:true})
check('wakes_and_waves_with_independent_wrist',()=>{assert(previous.sit<.001);assert(previous.wave>.999);assert(Math.abs(rig.arms[0].wrist.rotation.y)>.001)})
check('mouse_tracking_is_bounded',()=>{assert(previous.lookX<-.99);assert(Math.abs(rig.head.rotation.y)<.4);assert(Math.abs(rig.head.rotation.x)<.3)})
for(const action of ['idle','blink','wave','stretch','sitting','dozing','greeting','thinking','reminder','complete','unavailable','listening','speaking']){
 for(let i=0;i<90;i++)anim.update(action,1/30)
 check('finite_pose_'+action,()=>rig.root.traverse(o=>assert([...o.position.toArray(),...o.quaternion.toArray(),...o.scale.toArray()].every(Number.isFinite),o.name)))
}
function atRate(rate){
 const r=createPengxiaozhi(),a=createRobotAnimator(r);let pose
 for(let i=0;i<rate*2;i++)pose=a.update('sitting',1/rate)
 r.dispose();return pose
}
check('frame_rate_independent_transition',()=>assert(Math.abs(atRate(30).sit-atRate(60).sit)<.0001))
const bytes=await readFile(new URL('../public/assistant/pengxiaozhi-rigged.glb',import.meta.url))
const model=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')
check('exported_glb_has_real_meshes_and_twelve_animation_clips',()=>{assert.equal(model.animations.length,12);assert(model.scene.getObjectByName('FaceScreen'));assert(model.scene.getObjectByName('ShoulderRight'));assert(model.animations.find(a=>a.name==='SitDown').tracks.length>8)})
const mixer=new AnimationMixer(model.scene)
mixer.clipAction(model.animations.find(a=>a.name==='Sitting')).play();mixer.update(.6)
check('exported_sitting_clip_works_without_playing_transition_first',()=>{assert(Math.abs(model.scene.getObjectByName('HipRight').rotation.x+1.9)<.01);assert(model.scene.getObjectByName('Hips').position.y<.34)})
mixer.stopAllAction();mixer.clipAction(model.animations.find(a=>a.name==='Idle')).play();mixer.update(.6)
check('exported_idle_clip_restores_standing_pose',()=>{assert(Math.abs(model.scene.getObjectByName('HipRight').rotation.x)<.01);assert(model.scene.getObjectByName('Hips').position.y>.75)})
rig.dispose()
await writeFile(new URL('../../assistant_release_20261015/three_d/animation_results.json',import.meta.url),JSON.stringify({results,maxHipStep,maxFloorError},null,2))
console.log('ANIMATION CHECKS PASSED',results.length)

