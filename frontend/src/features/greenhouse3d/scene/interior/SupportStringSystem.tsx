import { useMemo } from 'react'
import * as THREE from 'three'
import type { CropInstance } from '../generation/cropGenerator'
import { cropProfiles } from '../config/cropProfiles'
import type { GrowthStage } from '../../../../types/cropBatch'

export default function SupportStringSystem({ instances, growthStage }: { instances: CropInstance[]; growthStage: GrowthStage | null }) {
  const geometry = useMemo(() => {
    const pts: number[] = []
    const p = new THREE.Vector3()
    instances.forEach((instance, index) => {
      if (growthStage === '苗期' || growthStage === '营养生长期') return
      if (cropProfiles[instance.crop].supportType !== 'twine') return
      // Use every other support line: visually cleaner while still communicating the training system.
      if (index % 2 !== 0) return
      p.setFromMatrixPosition(instance.matrix)
      pts.push(p.x, p.y + 1.05, p.z, p.x, 4.34, p.z)
    })
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    return g
  }, [instances, growthStage])

  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color="#d9dbd8" transparent opacity={0.42} />
    </lineSegments>
  )
}
