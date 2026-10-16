import { Clone, useGLTF } from '@react-three/drei'

export default function DeviceAssetLoader({
  type,
  id,
  position,
  onClick,
}: {
  type: 'sensor' | 'light' | 'sprinkler' | 'pump'
  id: string
  position: [number, number, number]
  onClick?: () => void
}) {
  const path = type === 'sensor'
    ? '/3d-assets/devices_v3/sensor_th_v3.glb'
    : type === 'pump'
      ? '/3d-assets/devices/pump.glb'
      : type === 'light'
        ? '/3d-assets/devices_v3/grow_light_v3.glb'
        : '/3d-assets/devices_v3/sprinkler_v3.glb'
  const { scene } = useGLTF(path)
  return (
    <group position={position} userData={{ g3dDeviceId: id }} onClick={(e) => { if (e.button !== 0 || e.delta >= 5) return; e.stopPropagation(); onClick?.() }}>
      <Clone object={scene} />
      <mesh>
        <sphereGeometry args={[type === 'pump' ? 0.65 : 0.48, 8, 6]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
    </group>
  )
}
