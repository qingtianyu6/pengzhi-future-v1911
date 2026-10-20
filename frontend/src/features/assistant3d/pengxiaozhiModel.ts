import * as THREE from 'three'
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js'
import { MarchingCubes } from 'three/addons/objects/MarchingCubes.js'

export type RobotRig = ReturnType<typeof createPengxiaozhi>

/** Original, editable 3D robot. Rigid parts use a joint hierarchy, appropriate for a mechanical character. */
export function createPengxiaozhi() {
  const root = new THREE.Group(); root.name = 'Pengxiaozhi'
  const cream = new THREE.MeshPhysicalMaterial({ color: '#fff0d8', roughness: .32, metalness: 0, clearcoat: .55, clearcoatRoughness: .24 })
  const green = new THREE.MeshPhysicalMaterial({ color: '#075337', roughness: .30, metalness: 0, clearcoat: .7, clearcoatRoughness: .2 })
  const dark = new THREE.MeshPhysicalMaterial({ color: '#032b20', roughness: .14, metalness: 0, clearcoat: 1, clearcoatRoughness: .13 })
  const sole = new THREE.MeshStandardMaterial({ color: '#0c4d3b', roughness: .65 })
  const straw = new THREE.MeshStandardMaterial({ color: '#dba54d', roughness: .78 })
  const weave = new THREE.MeshStandardMaterial({ color: '#ab7633', roughness: .85 })
  const mint = new THREE.MeshBasicMaterial({ color: '#92f3bc', toneMapped: false })
  const glow = new THREE.MeshBasicMaterial({ color: '#e8fff2', toneMapped: false })
  const pupilMat = new THREE.MeshBasicMaterial({ color: '#06472d', toneMapped: false })
  const leafMat = new THREE.MeshPhysicalMaterial({ color: '#39872c', roughness: .42, clearcoat: .35, side: THREE.DoubleSide })
  const veinMat = new THREE.MeshStandardMaterial({ color: '#98b958', roughness: .7 })
  const sphere = new THREE.SphereGeometry(1, 40, 24)
  const meshes: THREE.Mesh[] = []
  const skinnedLimbs: THREE.SkinnedMesh[] = []
  const legLengths={upper:.17,lower:.13}
  function mesh(parent: THREE.Object3D, geometry: THREE.BufferGeometry, material: THREE.Material, position: [number, number, number], scale: [number, number, number] = [1,1,1], name = '') {
    const item = new THREE.Mesh(geometry, material)
    item.castShadow=!(material instanceof THREE.MeshBasicMaterial);item.receiveShadow=true
    item.position.set(...position); item.scale.set(...scale); item.name = name
    parent.add(item); meshes.push(item); return item
  }
  const ball = (parent: THREE.Object3D, material: THREE.Material, pos: [number,number,number], scale: [number,number,number], name = '') => mesh(parent, sphere, material, pos, scale, name)
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
      const x=width/2*Math.sign(c)*Math.pow(Math.abs(c),.56),y=height/2*Math.sign(s)*Math.pow(Math.abs(s),.56)
      if(i===0)shape.moveTo(x,y);else shape.lineTo(x,y)
    }
    shape.closePath()
    const geo=new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSize:bevel,bevelThickness:bevel,bevelSegments:10,steps:1,curveSegments:24})
    geo.translate(0,0,-depth/2)
    geo.deleteAttribute('normal');geo.deleteAttribute('uv')
    const smooth=mergeVertices(geo);geo.dispose();smooth.computeVertexNormals()
    return smooth
  }
  // Continuous sculpted profiles replace the visible stacks of primitive beads.
  function shell(points: number[][], segments = 40) {
    const curve = new THREE.SplineCurve(points.map(([r,y]) => new THREE.Vector2(r,y)))
    return new THREE.LatheGeometry(curve.getPoints(40).map(p => new THREE.Vector2(Math.max(0,p.x),p.y)),segments)
  }
  function softLimb(parent:THREE.Object3D, bones:THREE.Bone[], origin:[number,number,number], length:number, radius:number, material:THREE.Material, name:string) {
    const positions:number[]=[],weights:number[]=[],skinIndices:number[]=[],indices:number[]=[]
    const rings=36,sides=28
    for(let i=0;i<=rings;i++) {
      const t=i/rings,d=-.035+(length+.035)*t
      const cap=Math.min(1,Math.sin(Math.PI*t)*5)
      const r=(radius*(.77+.25*Math.sin(Math.PI*t)))*Math.max(0,cap)
      const hinge=Math.abs(bones[1].position.y)
      const blend=THREE.MathUtils.smoothstep(d,hinge*.55,hinge+(length-hinge)*.55)
      for(let j=0;j<=sides;j++) {
        const a=j/sides*Math.PI*2
        positions.push(origin[0]+Math.cos(a)*r,origin[1]-d,origin[2]+Math.sin(a)*r*.92)
        weights.push(1-blend,blend,0,0);skinIndices.push(0,1,0,0)
        if(i<rings&&j<sides){const n=i*(sides+1)+j;indices.push(n,n+1,n+sides+1,n+1,n+sides+2,n+sides+1)}
      }
    }
    const geo=new THREE.BufferGeometry()
    geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3))
    geo.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skinIndices,4))
    geo.setAttribute('skinWeight',new THREE.Float32BufferAttribute(weights,4))
    geo.setIndex(indices);geo.computeVertexNormals()
    const item=new THREE.SkinnedMesh(geo,material)
    item.name=name;item.castShadow=true;item.receiveShadow=true
    parent.add(item);root.updateMatrixWorld(true)
    item.bind(new THREE.Skeleton(bones))
    item.frustumCulled=false
    meshes.push(item);skinnedLimbs.push(item)
    return item
  }
  function glove() {
    // A single implicit surface fuses palm, thumb and fingers without intersecting seams.
    const surface = new MarchingCubes(28,green,false,false,8000)
    surface.isolation=24
    surface.reset()
    for (const [x,y,z,strength] of [[.50,.50,.50,1],[.50,.60,.50,.45],[.35,.34,.50,.36],[.50,.29,.50,.38],[.64,.34,.50,.36],[.75,.52,.52,.35]]) surface.addBall(x,y,z,strength,12)
    surface.update()
    const count=surface.geometry.drawRange.count
    const geo=new THREE.BufferGeometry()
    geo.setAttribute('position',new THREE.Float32BufferAttribute(surface.geometry.getAttribute('position').array.slice(0,count*3),3))
    geo.setAttribute('normal',new THREE.Float32BufferAttribute(surface.geometry.getAttribute('normal').array.slice(0,count*3),3))
    geo.normalizeNormals();geo.scale(.29,.34,.22);geo.translate(0,-.08,0)
    surface.geometry.dispose()
    return geo
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
  const pelvis = joint(root, 'Hips', [0,.31+legLengths.upper+legLengths.lower,0])
  ball(pelvis,green,[0,-.02,0],[.34,.19,.25],'HipShell')
  const torso = joint(pelvis,'Torso',[0,0,0])
  mesh(torso,shell([[0,-.18],[.28,-.15],[.43,-.07],[.50,.10],[.51,.28],[.46,.51],[.32,.66],[.17,.70],[0,.69]]),cream,[0,0,0],[1,1,.80],'BodyShell')
  // A small waist band and raised leaf crest give the body real depth.
  ball(torso,green,[0,-.12,0],[.32,.045,.25],'WaistBand')
  const badge = leaf(torso,[-.035,.23,.39],.49,-.35); badge.name = 'ChestLeaf'
  const neck = joint(torso,'Neck',[0,.75,0])
  mesh(neck,new THREE.CylinderGeometry(.17,.19,.18,16),green,[0,0,0])
  const head = joint(neck,'Head',[0,0,0])
  mesh(head,faceShape(1.55,1.08,.55,.105),cream,[0,.39,0],[1,1,1],'HeadShell')
  mesh(head,faceShape(1.38,.91,.035,.025),green,[0,.39,.397],[1,1,1],'FaceFrame')
  const faceVertices:number[]=[0,0,.085],faceIndices:number[]=[]
  for(let r=1;r<=16;r++)for(let j=0;j<64;j++){
    const a=j/64*Math.PI*2,c=Math.cos(a),s=Math.sin(a),f=r/16
    faceVertices.push(.676*f*Math.sign(c)*Math.pow(Math.abs(c),.56),.442*f*Math.sign(s)*Math.pow(Math.abs(s),.56),.085*(1-f*f))
  }
  for(let j=0;j<64;j++)faceIndices.push(0,j+1,(j+1)%64+1)
  for(let r=0;r<15;r++)for(let j=0;j<64;j++){
    const a=1+r*64+j,b=1+r*64+(j+1)%64,c=a+64,d=b+64
    faceIndices.push(a,c,b,b,c,d)
  }
  const faceGeo=new THREE.BufferGeometry();faceGeo.setAttribute('position',new THREE.Float32BufferAttribute(faceVertices,3));faceGeo.setIndex(faceIndices);faceGeo.computeVertexNormals()
  mesh(head,faceGeo,dark,[0,.40,.45],[1,1,1],'FaceScreen')
  ball(head,green,[-.79,.38,-.055],[.10,.22,.20],'EarRight')
  ball(head,green,[.79,.38,-.055],[.10,.22,.20],'EarLeft')
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
  const profile = [[0,.86],[.68,.86],[.90,.82],[1.02,.83],[1.06,.855],[1.055,.885],[1.02,.91],[.94,.935],[.82,.965],[.73,.99]]
  for(let i=0;i<=12;i++){const y=.98+i*.036;profile.push([.73*Math.sqrt(Math.max(0,1-Math.pow((y-.95)/.47,2))),y])}
  profile.push([0,1.42])
  const hat = group(head,'StrawHat',[0,0,0]); hat.rotation.z = -.07
  mesh(hat,shell(profile,64),straw,[0,0,0],[1,1,.83],'WovenHatShell')
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
  for(let i=0;i<9;i++) addRing(.74+i*.036,.99-(.01+i*.036)*.24,.005)
  for(let i=0;i<40;i++) {
    const a=i/40*Math.PI*2; const points=[]
    for(let j=0;j<=10;j++) {
      const y=1.08+j*.032;const r=.734*Math.sqrt(Math.max(0,1-Math.pow((y-.95)/.47,2)))
      points.push(new THREE.Vector3(Math.cos(a+.04*j)*r,y,Math.sin(a+.04*j)*r*.83))
    }
    ridges.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),10,.0035,3,false))
    const brimPoints=[]
    for(let j=0;j<=5;j++){const r=.74+j*.059;brimPoints.push(new THREE.Vector3(Math.cos(a)*r,.99-(r-.73)*.24,Math.sin(a)*r*.83))}
    ridges.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(brimPoints),5,.003,3,false))
  }
  // Alternating diagonal strands create a woven read instead of straight lathe grooves.
  for(let row=0;row<10;row++)for(let i=0;i<36;i++) {
    const points=[]
    for(let j=0;j<=4;j++) {
      const y=1.09+row*.027+j*.0065
      const a=(i+(row%2)*.5)/36*Math.PI*2+(row%2===0?1:-1)*j*.024
      const r=.739*Math.sqrt(Math.max(0,1-Math.pow((y-.95)/.47,2)))
      points.push(new THREE.Vector3(Math.cos(a)*r,y,Math.sin(a)*r*.83))
    }
    ridges.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),4,.003,3,false))
  }
  const merged=mergeGeometries(ridges); if(merged) mesh(hat,merged,weave,[0,0,0]); ridges.forEach(g=>g.dispose())
  mesh(hat,new THREE.LatheGeometry([.96,.98,1,1.02,1.04,1.06,1.08].map(y=>new THREE.Vector2(.737*Math.sqrt(1-Math.pow((y-.95)/.47,2)),y)),48),green,[0,0,0],[1,1,.83],'HatRibbon')
  leaf(hat,[.65,1.12,.14],.78,-.68)
  const gloveGeometry=glove()
  const arms = [-1,1].map((side) => {
    const shoulder = joint(torso,side===-1?'ShoulderRight':'ShoulderLeft',[side*.55,.53,0])
    ball(shoulder,green,[0,.015,-.01],[.14,.13,.145],'ShoulderSocket')
    const elbow = joint(shoulder,side===-1?'ElbowRight':'ElbowLeft',[0,-.21,0])
    const wrist=joint(elbow,side===-1?'WristRight':'WristLeft',[0,-.19,0])
    softLimb(torso,[shoulder,elbow],[side*.55,.53,0],.40,.18,cream,side===-1?'SoftArmRight':'SoftArmLeft')
    ball(wrist,green,[0,-.015,0],[.11,.10,.105],'WristCuff')
    mesh(wrist,gloveGeometry,green,[0,-.005,.02],[side,1,1],'SculptedGlove')
    return {shoulder,elbow,wrist}
  })
  const legs = [-1,1].map((side) => {
    const hip=joint(pelvis,side===-1?'HipRight':'HipLeft',[side*.255,-.03,0])
    const knee=joint(hip,side===-1?'KneeRight':'KneeLeft',[0,-legLengths.upper,0])
    const ankle=joint(knee,side===-1?'AnkleRight':'AnkleLeft',[0,-legLengths.lower,0])
    softLimb(pelvis,[hip,knee],[side*.255,-.03,0],legLengths.upper+legLengths.lower,.16,green,side===-1?'SoftLegRight':'SoftLegLeft')
    const boot=shell([[0,-.25],[.19,-.25],[.235,-.22],[.25,-.17],[.245,-.115],[.21,-.07],[.165,-.025],[.16,.075],[.15,.13],[0,.13]])
    const bootPositions=boot.getAttribute('position')
    for(let i=0;i<bootPositions.count;i++) {
      const toe=1-THREE.MathUtils.smoothstep(bootPositions.getY(i),-.18,.035)
      bootPositions.setZ(i,bootPositions.getZ(i)*(1.1+.3*toe)+.15*toe)
    }
    boot.computeVertexNormals()
    mesh(ankle,boot,green,[0,0,0],[1,1,1],'Boot')
    mesh(ankle,shell([[0,-.28],[.18,-.28],[.233,-.27],[.238,-.245],[.23,-.23],[0,-.23]]),sole,[0,0,.11],[1,1,1.34],'BootSole')
    return {hip,knee,ankle}
  })
  root.rotation.y=-.24
  root.userData={ name:'棚小智', version:'2.1-continuous-limbs', author:'棚智未来', rig:'Mechanical joints with continuous skinned limbs', license:'Project original asset' }
  function dispose() {
    const geometries=new Set<THREE.BufferGeometry>();const materials=new Set<THREE.Material>()
    meshes.forEach(m=>{geometries.add(m.geometry);if(Array.isArray(m.material))m.material.forEach(v=>materials.add(v));else materials.add(m.material)})
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());skinnedLimbs.forEach(m=>m.skeleton.dispose())
  }
  return {root,pelvis,torso,head,eyes,mouth,arms,legs,legLengths,skinnedLimbs,dispose}
}

