export default function PipeSystem({ sprinklers }: { sprinklers: number }) {
  return (
    <group>
      <mesh position={[0, 4.48, 0.35]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.018, 0.018, 29, 8]} />
        <meshStandardMaterial color="#5b6b72" roughness={0.58} />
      </mesh>
      {Array.from({ length: sprinklers }, (_, i) => {
        const x = -13.5 + i * (27 / Math.max(1, sprinklers - 1))
        return (
          <group key={i} position={[x, 0, 0.35]}>
            <mesh position={[0, 4.25, 0]}>
              <cylinderGeometry args={[0.007, 0.007, 0.40, 6]} />
              <meshStandardMaterial color="#526169" />
            </mesh>
            <mesh position={[0, 4.04, 0]}>
              <boxGeometry args={[0.075, 0.030, 0.030]} />
              <meshStandardMaterial color="#5e6b71" />
            </mesh>
            <mesh position={[0, 3.995, 0]}>
              <sphereGeometry args={[0.023, 8, 6]} />
              <meshStandardMaterial color="#68757b" />
            </mesh>
          </group>
        )
      })}
    </group>
  )
}
