import { useGLTF } from '@react-three/drei'
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { CropType } from '../config/types'
import type { CropInstance } from '../generation/cropGenerator'

const label = (v: number) => ['a', 'b', 'c'][v % 3]
const url = (c: CropType, v: number) => `/3d-assets/crops_v4/${c}_${label(v)}.glb`
const zUpToYUp = new THREE.Matrix4().makeRotationX(-Math.PI / 2)

type Part = {
  geometry: THREE.BufferGeometry
  material: THREE.Material
  local: THREE.Matrix4
  name: string
  fruitPart: boolean
}

export default function CropAssetLoader({ crop, variant, instances, onSelect }: { crop: CropType; variant: number; instances: CropInstance[]; onSelect: (bedId: string) => void }) {
  const gltf = useGLTF(url(crop, variant))
  const parts = useMemo(() => {
    const result: Part[] = []
    gltf.scene.updateMatrixWorld(true)
    const inv = new THREE.Matrix4().copy(gltf.scene.matrixWorld).invert()
    gltf.scene.traverse((o) => {
      if (!(o as THREE.Mesh).isMesh) return
      const mesh = o as THREE.Mesh
      const material = (mesh.material as THREE.Material).clone()
      if (material instanceof THREE.MeshStandardMaterial) {
        const m = material
        m.roughness = Math.max(0.58, m.roughness ?? 0.7)
        m.metalness = 0
        if (/leaves|outer|middle|heart/i.test(mesh.name)) m.color.multiply(new THREE.Color('#83b78a'))
        if (/stem/i.test(mesh.name)) m.color.multiply(new THREE.Color('#78a479'))
        if (/fruitred/i.test(mesh.name)) m.color.multiply(new THREE.Color('#bd9b94'))
        if (/fruitgreen/i.test(mesh.name)) m.color.multiply(new THREE.Color('#aeb9a2'))
        if (/fruitmid/i.test(mesh.name)) m.color.multiply(new THREE.Color('#bca99b'))
      }
      result.push({
        geometry: mesh.geometry,
        material,
        local: new THREE.Matrix4().multiplyMatrices(zUpToYUp, new THREE.Matrix4().multiplyMatrices(inv, mesh.matrixWorld)),
        name: mesh.uuid,
        fruitPart: /fruit|calyx/i.test(mesh.name),
      })
    })
    return result
  }, [gltf.scene])
  useEffect(() => () => parts.forEach((part) => part.material.dispose()), [parts])

  return <group>{parts.map((part) => <Part key={part.name} part={part} instances={instances} onSelect={onSelect} />)}</group>
}

function Part({ part, instances, onSelect }: { part: Part; instances: CropInstance[]; onSelect: (bedId: string) => void }) {
  const ref = useRef<THREE.InstancedMesh>(null!)
  useLayoutEffect(() => {
    instances.forEach((instance, index) => {
      const matrix = new THREE.Matrix4().multiplyMatrices(instance.matrix, part.local)
      if (part.fruitPart && !instance.fruitVisible) matrix.scale(new THREE.Vector3(0, 0, 0))
      ref.current.setMatrixAt(index, matrix)
    })
    ref.current.instanceMatrix.needsUpdate = true
    ref.current.computeBoundingSphere()
  }, [instances, part])

  return (
    <instancedMesh ref={ref} args={[part.geometry, part.material, instances.length]} userData={{ g3dBedIds: instances.map((instance) => instance.bedId) }} castShadow={false} receiveShadow onClick={(event) => {
      if (event.button !== 0 || event.delta >= 5) return
      event.stopPropagation()
      const bedId = instances[event.instanceId ?? -1]?.bedId
      if (bedId) onSelect(bedId)
    }} />
  )
}
