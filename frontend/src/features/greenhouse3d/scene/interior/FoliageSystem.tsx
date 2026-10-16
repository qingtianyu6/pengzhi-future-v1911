import { useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { CropInstance } from '../generation/cropGenerator'

function makeLeafGeometry() {
  const positions: number[] = []
  const colors: number[] = []
  const indices: number[] = []
  const segments = 8
  for (let step = 0; step <= segments; step++) {
    const t = step / segments
    const width = Math.pow(Math.sin(Math.PI * t), 0.8) * (1 + 0.035 * Math.sin(t * Math.PI * 9))
    for (const across of [-1, 0, 1]) {
      positions.push(-1 + t * 2, 0.42 * (1 - Math.abs(across)) + 0.14 * t * t, across * width)
      const vein = across === 0 ? 1.06 : 0.79
      const tip = 0.90 + 0.10 * Math.sin(Math.PI * t)
      colors.push(0.86 * vein * tip, 1.0 * vein * tip, 0.78 * vein * tip)
    }
    if (step === segments) continue
    const a = step * 3
    indices.push(a, a + 3, a + 1, a + 1, a + 3, a + 4)
    indices.push(a + 1, a + 4, a + 2, a + 2, a + 4, a + 5)
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  return geometry
}

const leafGeometry = makeLeafGeometry()

function LeafCluster({ instances, shade, compact = false, onSelect }: { instances: CropInstance[]; shade: 0 | 1; compact?: boolean; onSelect: (bedId: string) => void }) {
  const ref = useRef<THREE.InstancedMesh>(null)
  const leavesPerPlant = compact ? 1 : 2
  const matrices = useMemo(() => instances.flatMap((instance, index) =>
    Array.from({ length: leavesPerPlant }, (_, leafIndex) => {
      const phase = Math.sin(index * 12.9898 + shade * 4.13 + leafIndex * 7.39)
      const side = shade ? 1 : -1
      const y = compact
        ? 0.24 + shade * 0.08 + phase * 0.04
        : 0.48 + shade * 0.23 + leafIndex * 0.63 + phase * 0.12
      const local = new THREE.Matrix4().compose(
        new THREE.Vector3(side * (compact ? 0.075 : 0.16 + phase * 0.04), y, phase * (compact ? 0.05 : 0.12)),
        new THREE.Quaternion().setFromEuler(new THREE.Euler(0.55 + phase * 0.28, index * 2.4 + shade + leafIndex, side * 0.42)),
        new THREE.Vector3(compact ? 0.085 : 0.13, 0.027, compact ? 0.047 : 0.062),
      )
      return new THREE.Matrix4().multiplyMatrices(instance.matrix, local)
    })), [instances, shade, compact, leavesPerPlant])

  useLayoutEffect(() => {
    if (!ref.current) return
    matrices.forEach((matrix, index) => ref.current?.setMatrixAt(index, matrix))
    ref.current.instanceMatrix.needsUpdate = true
    ref.current.computeBoundingSphere()
  }, [matrices])

  if (!matrices.length) return null
  return <instancedMesh ref={ref} args={[undefined, undefined, matrices.length]} onClick={(event) => {
    if (event.button !== 0 || event.delta >= 5) return
    const bedId = instances[Math.floor((event.instanceId ?? -1) / leavesPerPlant)]?.bedId
    if (bedId) { event.stopPropagation(); onSelect(bedId) }
  }}>
    <primitive object={leafGeometry} attach="geometry" />
    <meshStandardMaterial color={shade ? '#4d9157' : '#3f8051'} vertexColors roughness={0.92} side={THREE.DoubleSide} />
  </instancedMesh>
}

export default function FoliageSystem({ instances, onSelect }: { instances: CropInstance[]; onSelect: (bedId: string) => void }) {
  const vines = useMemo(() => instances.filter((instance) =>
    instance.crop === 'tomato' || instance.crop === 'cucumber'
  ), [instances])
  const strawberries = useMemo(() => instances.filter((instance) => instance.crop === 'strawberry'), [instances])
  return <group>
    <LeafCluster instances={vines} shade={0} onSelect={onSelect} />
    <LeafCluster instances={vines} shade={1} onSelect={onSelect} />
    <LeafCluster instances={strawberries} shade={0} compact onSelect={onSelect} />
    <LeafCluster instances={strawberries} shade={1} compact onSelect={onSelect} />
  </group>
}
