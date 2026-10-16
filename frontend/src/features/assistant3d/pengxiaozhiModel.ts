import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'

export type RobotRig = ReturnType<typeof createPengxiaozhi>

/** Original, editable 3D robot. Rigid parts use a joint hierarchy, appropriate for a mechanical character. */
export function createPengxiaozhi() {
  const root = new THREE.Group(); root.name = 'Pengxiaozhi'
  const cream = new THREE.MeshPhysicalMaterial({ color: '#fff0d7', roughness: .29, metalness: 0, clearcoat: .4 })
  const green = new THREE.MeshPhysicalMaterial({ color: '#075335', roughness: .25, metalness: .03, clearcoat: .65 })
  const dark = new THREE.MeshPhysicalMaterial({ color: '#022a1b', roughness: .20, metalness: 0, clearcoat: 1 })
  const sole = new THREE.MeshStandardMaterial({ color: '#0c4d3b', roughness: .65 })
  const straw = new THREE.MeshStandardMaterial({ color: '#dba54d', roughness: .78 })
  const weave = new THREE.MeshStandardMaterial({ color: '#ab7633', roughness: .85 })
  const mint = new THREE.MeshBasicMaterial({ color: '#92f3bc', toneMapped: false })
  const glow = new THREE.MeshBasicMaterial({ color: '#e8fff2', toneMapped: false })
  const pupilMat = new THREE.MeshBasicMaterial({ color: '#06472d', toneMapped: false })
  const leafMat = new THREE.MeshPhysicalMaterial({ color: '#39872c', roughness: .42, clearcoat: .35, side: THREE.DoubleSide })
  const veinMat = new THREE.MeshStandardMaterial({ color: '#98b958', roughness: .7 })
  const sphere = new THREE.SphereGeometry(1, 32, 20)
  const round = new RoundedBoxGeometry(1, 1, 1, 3, .22)
  const capsule = new THREE.CapsuleGeometry(1, 1, 4, 12)
  const meshes: THREE.Mesh[] = []
  function mesh(parent: THREE.Object3D, geometry: THREE.BufferGeometry, material: THREE.Material, position: [number, number, number], scale: [number, number, number] = [1,1,1], name = '') {
    const item = new THREE.Mesh(geometry, material)
    item.castShadow=!(material instanceof THREE.MeshBasicMaterial);item.receiveShadow=true
    item.position.set(...position); item.scale.set(...scale); item.name = name
    parent.add(item); meshes.push(item); return item
  }
  const ball = (parent: THREE.Object3D, material: THREE.Material, pos: [number,number,number], scale: [number,number,number], name = '') => mesh(parent, sphere, material, pos, scale, name)
  const box = (parent: THREE.Object3D, material: THREE.Material, pos: [number,number,number], scale: [number,number,number], name = '') => mesh(parent, round, material, pos, scale, name)
  function group(parent: THREE.Object3D, name: string, pos: [number,number,number]) {
    const item = new THREE.Group(); item.name = name; item.position.set(...pos); parent.add(item); return item
  }
  function joint(parent: THREE.Object3D,name:string,pos:[number,number,number]) {
    const item=new THREE.Bone();item.name=name;item.position.set(...pos);parent.add(item);return item
  }
  function tube(parent: THREE.Object3D, points: THREE.Vector3[], radius: number, material: THREE.Material, segments = 18) {
    return mesh(parent, new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), segments, radius, 5, false), material, [0,0,0])
  }
  function faceShape(width:number,height:number,depth:number,bevel:number) {
    const shape=new THREE.Shape()
    for(let i=0;i<=96;i++) {
      const t=i/96*Math.PI*2,c=Math.cos(t),s=Math.sin(t)
      const x=width/2*Math.sign(c)*Math.pow(Math.abs(c),.8),y=height/2*Math.sign(s)*Math.pow(Math.abs(s),.8)
      if(i===0)shape.moveTo(x,y);else shape.lineTo(x,y)
    }
    shape.closePath()
    const geo=new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSize:bevel,bevelThickness:bevel,bevelSegments:10,steps:1,curveSegments:24})
    geo.translate(0,0,-depth/2)
    geo.deleteAttribute('normal');geo.deleteAttribute('uv')
    const smooth=mergeVertices(geo);geo.dispose();smooth.computeVertexNormals()
    return smooth
  }
  function leaf(parent: THREE.Object3D, pos: [number,number,number], scale: number, angle: number) {
    const item = group(parent, 'Leaf', pos); item.scale.setScalar(scale); item.rotation.z = angle
    const vertices:number[]=[],indices:number[]=[]
    for(let i=0;i<=20;i++)for(let j=0;j<=8;j++){
      const t=i/20,u=j/4-1,w=.17*Math.pow(Math.sin(Math.PI*t),.8)
      vertices.push(u*w+.055*t,.66*t,.08*(1-u*u)*Math.sin(Math.PI*t)+.035*t*t)
    }
    for(let i=0;i<20;i++)for(let j=0;j<8;j++){const a=i*9+j;indices.push(a,a+1,a+9,a+1,a+10,a+9)}
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));geo.setIndex(indices);geo.computeVertexNormals()
    mesh(item,geo,leafMat,[0,0,0])
    tube(item,[new THREE.Vector3(0,0,.008),new THREE.Vector3(.027,.33,.095),new THREE.Vector3(.055,.65,.047)],.006,veinMat)
    for (const y of [.16,.28,.4]) for (const side of [-1,1]) {
      tube(item,[new THREE.Vector3(y*.08,y,.08*Math.sin(y/.66*Math.PI)+.012),new THREE.Vector3(side*.11+(y+.1)*.08,y+.1,.035)],.003,veinMat,5)
    }
    return item
  }
  const pelvis = joint(root, 'Hips', [0,.76,0])
  ball(pelvis,green,[0,-.02,0],[.37,.26,.29],'HipShell')
  const torso = joint(pelvis,'Torso',[0,0,0])
  ball(torso,cream,[0,.30,0],[.55,.55,.39],'BodyShell')
  // A small waist band and raised leaf crest give the body real depth.
  ball(torso,green,[0,-.10,0],[.39,.08,.29],'WaistBand')
  const badge = leaf(torso,[-.035,.23,.39],.49,-.35); badge.name = 'ChestLeaf'
  const neck = joint(torso,'Neck',[0,.75,0])
  mesh(neck,new THREE.CylinderGeometry(.17,.19,.18,16),green,[0,0,0])
  const head = joint(neck,'Head',[0,0,0])
  mesh(head,faceShape(1.55,1.04,.54,.105),cream,[0,.39,0],[1,1,1],'HeadShell')
  mesh(head,faceShape(1.39,.88,.06,.035),green,[0,.39,.395],[1,1,1],'FaceFrame')
  const faceVertices:number[]=[0,0,.085],faceIndices:number[]=[]
  for(let r=1;r<=16;r++)for(let j=0;j<64;j++){
    const a=j/64*Math.PI*2,c=Math.cos(a),s=Math.sin(a),f=r/16
    faceVertices.push(.681*f*Math.sign(c)*Math.pow(Math.abs(c),.8),.436*f*Math.sign(s)*Math.pow(Math.abs(s),.8),.085*(1-f*f))
  }
  for(let j=0;j<64;j++)faceIndices.push(0,j+1,(j+1)%64+1)
  for(let r=0;r<15;r++)for(let j=0;j<64;j++){
    const a=1+r*64+j,b=1+r*64+(j+1)%64,c=a+64,d=b+64
    faceIndices.push(a,c,b,b,c,d)
  }
  const faceGeo=new THREE.BufferGeometry();faceGeo.setAttribute('position',new THREE.Float32BufferAttribute(faceVertices,3));faceGeo.setIndex(faceIndices);faceGeo.computeVertexNormals()
  mesh(head,faceGeo,dark,[0,.40,.45],[1,1,1],'FaceScreen')
  ball(head,green,[-.80,.38,-.04],[.13,.25,.24],'EarRight')
  ball(head,green,[.80,.38,-.04],[.13,.25,.24],'EarLeft')
  const eyes = [-1,1].map((side) => {
    const eye = group(head,side === -1 ? 'EyeRight' : 'EyeLeft',[side*.31,.49,.544])
    ball(eye,mint,[0,0,0],[.125,.167,.024])
    ball(eye,pupilMat,[.028,-.010,.023],[.060,.109,.016])
    ball(eye,glow,[-.022,.055,.043],[.026,.04,.007])
    return eye
  })
  const mouth = group(head,'Mouth',[0,.24,.545])
  tube(mouth,[new THREE.Vector3(-.13,.04,0),new THREE.Vector3(-.08,-.012,.003),new THREE.Vector3(0,-.035,.004),new THREE.Vector3(.08,-.012,.003),new THREE.Vector3(.13,.04,0)],.018,mint,28)
  // Lathed hat crown and brim; woven ridges are merged into a single draw call.
  const profile = [[0,.85],[.68,.85],[.91,.79],[1.03,.80],[1.06,.83],[1.035,.87],[.94,.90],[.73,.97]]
  for(let i=0;i<=12;i++){const y=.98+i*.036;profile.push([.73*Math.sqrt(Math.max(0,1-Math.pow((y-.95)/.47,2))),y])}
  profile.push([0,1.42])
  const hat = group(head,'StrawHat',[0,0,0]); hat.rotation.z = -.07
  mesh(hat,new THREE.LatheGeometry(profile.map(([x,y])=>new THREE.Vector2(x,y)),48),straw,[0,0,0],[1,1,.83])
  const ridges: THREE.BufferGeometry[] = []
  const addRing = (radius:number,y:number,thickness:number) => {
    const geo = new THREE.TorusGeometry(radius,thickness,4,48)
    geo.rotateX(Math.PI/2); geo.scale(1,1,.83); geo.translate(0,y,0); ridges.push(geo)
  }
  for (let i=0;i<18;i++) {
    const y=1.08+i*.019
    const radius=.731*Math.sqrt(Math.max(0,1-Math.pow((y-.95)/.47,2)))
    addRing(radius,y,.006)
  }
  for(let i=0;i<9;i++) addRing(.74+i*.036,.97-(.01+i*.036)*.328+.005,.005)
  for(let i=0;i<40;i++) {
    const a=i/40*Math.PI*2; const points=[]
    for(let j=0;j<=10;j++) {
      const y=1.08+j*.032;const r=.734*Math.sqrt(Math.max(0,1-Math.pow((y-.95)/.47,2)))
      points.push(new THREE.Vector3(Math.cos(a+.04*j)*r,y,Math.sin(a+.04*j)*r*.83))
    }
    ridges.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),10,.0035,3,false))
    const brimPoints=[]
    for(let j=0;j<=5;j++){const r=.74+j*.059;brimPoints.push(new THREE.Vector3(Math.cos(a)*r,.975-(r-.73)*.328,Math.sin(a)*r*.83))}
    ridges.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(brimPoints),5,.003,3,false))
  }
  const merged=mergeGeometries(ridges); if(merged) mesh(hat,merged,weave,[0,0,0]); ridges.forEach(g=>g.dispose())
  mesh(hat,new THREE.LatheGeometry([.96,.98,1,1.02,1.04,1.06,1.08].map(y=>new THREE.Vector2(.737*Math.sqrt(1-Math.pow((y-.95)/.47,2)),y)),48),green,[0,0,0],[1,1,.83],'HatRibbon')
  leaf(hat,[.65,1.12,.14],.78,-.68)
  const arms = [-1,1].map((side) => {
    const shoulder = joint(torso,side===-1?'ShoulderRight':'ShoulderLeft',[side*.52,.56,0])
    ball(shoulder,green,[0,0,0],[.19,.19,.20])
    mesh(shoulder,capsule,cream,[0,-.14,0],[.17,.11,.175])
    const elbow = joint(shoulder,side===-1?'ElbowRight':'ElbowLeft',[0,-.25,0])
    ball(elbow,green,[0,0,0],[.135,.135,.135])
    ball(elbow,cream,[0,-.09,.02],[.17,.17,.175])
    const wrist=joint(elbow,side===-1?'WristRight':'WristLeft',[0,-.22,0])
    ball(wrist,green,[0,-.07,0],[.17,.17,.14])
    for(let i=0;i<3;i++) mesh(wrist,capsule,green,[(i-1)*.075,-.17,.025],[.048,.045,.065])
    const thumb=ball(wrist,green,[-side*.15,-.06,.045],[.065,.095,.075]); thumb.rotation.z=side*.55
    return {shoulder,elbow,wrist}
  })
  const legs = [-1,1].map((side) => {
    const hip=joint(pelvis,side===-1?'HipRight':'HipLeft',[side*.255,-.03,0])
    mesh(hip,capsule,cream,[0,-.11,0],[.17,.08,.17])
    const knee=joint(hip,side===-1?'KneeRight':'KneeLeft',[0,-.25,0])
    ball(knee,green,[0,0,0],[.14,.14,.14])
    ball(knee,green,[0,-.10,0],[.17,.15,.18])
    const ankle=joint(knee,side===-1?'AnkleRight':'AnkleLeft',[0,-.20,0])
    mesh(ankle,new RoundedBoxGeometry(.46,.33,.62,5,.13),green,[0,-.105,.12],[1,1,1],'Boot')
    box(ankle,sole,[0,-.255,.12],[.46,.05,.60],'BootSole')
    return {hip,knee,ankle}
  })
  root.rotation.y=-.24
  root.userData={ name:'棚小智', author:'棚智未来', rig:'Hierarchical rigid-part joints', license:'Project original asset' }
  function dispose() {
    const geometries=new Set<THREE.BufferGeometry>();const materials=new Set<THREE.Material>()
    meshes.forEach(m=>{geometries.add(m.geometry);if(Array.isArray(m.material))m.material.forEach(v=>materials.add(v));else materials.add(m.material)})
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose())
  }
  return {root,pelvis,torso,head,eyes,mouth,arms,legs,dispose}
}

