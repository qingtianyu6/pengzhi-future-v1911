import { OrthographicCamera, PerspectiveCamera } from '@react-three/drei'
import * as THREE from 'three'

const presets: Record<string, { position: [number, number, number]; target: [number, number, number]; fov?: number }> = {
  entrance: { position: [-14.0, 1.70, -0.05], target: [9, 1.25, 0], fov: 57 },
  center: { position: [-1.8, 1.68, 0.08], target: [13, 1.25, 0], fov: 57 },
  zonea: { position: [-6.7, 1.62, -0.45], target: [-1.8, 1.0, -5.0], fov: 57 },
  zonec: { position: [4.0, 1.57, -0.40], target: [9.2, 0.72, -5.0], fov: 57 },
}

export default function PreviewCamera({ preset }: { preset: string }) {
  if (preset === 'top') {
    return (
      <OrthographicCamera
        makeDefault
        position={[0, 28, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        left={-18}
        right={18}
        top={10.7}
        bottom={-10.7}
        near={0.1}
        far={100}
      />
    )
  }
  const p = presets[preset] ?? presets.entrance
  return (
    <PerspectiveCamera
      makeDefault
      position={p.position}
      fov={p.fov ?? 57}
      near={0.1}
      far={100}
      onUpdate={(camera) => camera.lookAt(new THREE.Vector3(...p.target))}
    />
  )
}
