export default function LightingSystem({ count, on }: { count: number; on: boolean }) {
  const cols = Math.max(1, Math.ceil(count / 2))
  return (
    <group>
      {Array.from({ length: count }, (_, i) => {
        const row = i % 2
        const col = Math.floor(i / 2)
        const x = -13.2 + col * (26.4 / Math.max(1, cols - 1))
        const z = row === 0 ? -4.6 : 4.6
        return (
          <group key={i} position={[x, 4.25, z]}>
            <mesh castShadow={false}>
              <boxGeometry args={[1.90, 0.065, 0.14]} />
              <meshStandardMaterial color="#b2bdc1" metalness={0.72} roughness={0.25} />
            </mesh>
            <mesh position={[0, -0.045, 0]}>
              <boxGeometry args={[1.72, 0.022, 0.105]} />
              <meshStandardMaterial color="#efece5" emissive={on ? '#fff0d4' : '#000000'} emissiveIntensity={on ? 1.4 : 0} roughness={0.45} />
            </mesh>
            <mesh position={[-0.74, 0.105, 0]}>
              <boxGeometry args={[0.055, 0.15, 0.18]} />
              <meshStandardMaterial color="#808b8f" metalness={0.65} />
            </mesh>
            <mesh position={[0.74, 0.105, 0]}>
              <boxGeometry args={[0.055, 0.15, 0.18]} />
              <meshStandardMaterial color="#808b8f" metalness={0.65} />
            </mesh>
            {on && (
              <rectAreaLight
                color="#ffe3bc"
                intensity={3.2}
                width={3.1}
                height={1.8}
                position={[0, -0.16, 0]}
                rotation={[-Math.PI / 2, 0, 0]}
              />
            )}
          </group>
        )
      })}
    </group>
  )
}
