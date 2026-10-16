import { RoundedBox } from '@react-three/drei'
import type { BedLayout } from '../config/types'
import { cropProfiles } from '../config/cropProfiles'

export default function BedSystem({ beds, onSelect }: { beds: BedLayout[]; onSelect: (id: string) => void }) {
  return (
    <group>
      {beds.map((bed) => {
        const profile = cropProfiles[bed.crop]
        const aisleSide = bed.position[2] < 0 ? bed.size[2] / 2 + 0.075 : -bed.size[2] / 2 - 0.075
        return (
          <group key={bed.id} position={bed.position} userData={{ g3dBedId: bed.id }} onClick={(e) => { if (e.button !== 0 || e.delta >= 5) return; e.stopPropagation(); onSelect(bed.id) }}>
            <RoundedBox args={[bed.size[0], 0.135, bed.size[2]]} radius={0.035} smoothness={2} castShadow receiveShadow>
              <meshStandardMaterial color="#77766f" roughness={0.88} />
            </RoundedBox>
            <RoundedBox args={[bed.size[0] - 0.14, 0.10, bed.size[2] - 0.16]} radius={0.028} smoothness={2} position={[0, 0.13, 0]} receiveShadow>
              <meshStandardMaterial color="#493328" roughness={0.96} />
            </RoundedBox>
            <mesh position={[0, 0.10, -bed.size[2] / 2 + 0.03]}>
              <boxGeometry args={[bed.size[0], 0.18, 0.05]} />
              <meshStandardMaterial color="#77766e" roughness={0.80} />
            </mesh>
            <mesh position={[0, 0.10, bed.size[2] / 2 - 0.03]}>
              <boxGeometry args={[bed.size[0], 0.18, 0.05]} />
              <meshStandardMaterial color="#77766e" roughness={0.80} />
            </mesh>
            {Array.from({ length: profile.dripLines }, (_, i) => {
              const z = profile.dripLines === 1 ? 0 : (i === 0 ? -0.20 : 0.20)
              return (
                <mesh key={i} position={[0, 0.195, z]} rotation={[0, 0, Math.PI / 2]}>
                  <cylinderGeometry args={[0.0042, 0.0042, bed.size[0] - 0.28, 8]} />
                  <meshStandardMaterial color="#24292b" roughness={0.86} />
                </mesh>
              )
            })}
            <mesh position={[0, -0.058, aisleSide]} receiveShadow>
              <boxGeometry args={[bed.size[0], 0.038, 0.075]} />
              <meshStandardMaterial color="#777f7d" roughness={0.76} />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}
