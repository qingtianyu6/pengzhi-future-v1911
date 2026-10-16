import { useThree } from '@react-three/fiber'
import { useEffect } from 'react'
import * as THREE from 'three'

type PickData = { g3dBedId?: string; g3dBedIds?: string[]; g3dDeviceId?: string; g3dExterior?: boolean }

export default function ScenePicker({ onBed, onDevice, onExterior }: {
  onBed: (id: string) => void
  onDevice: (id: string) => void
  onExterior: () => void
}) {
  const { gl, camera, scene } = useThree()

  useEffect(() => {
    const canvas = gl.domElement
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let press: { id: number; x: number; y: number } | null = null

    const pick = (event: PointerEvent) => {
      if (event.button !== 0 || document.pointerLockElement || press?.id !== event.pointerId) return
      const moved = Math.hypot(event.clientX - press.x, event.clientY - press.y)
      press = null
      if (moved >= 5) return
      const rect = canvas.getBoundingClientRect()
      pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1)
      raycaster.setFromCamera(pointer, camera)

      const targets: THREE.Object3D[] = []
      scene.traverse((object) => {
        if (!(object as THREE.Mesh).isMesh) return
        for (let parent: THREE.Object3D | null = object; parent; parent = parent.parent) {
          const data = parent.userData as PickData
          if (data.g3dBedId || data.g3dBedIds || data.g3dDeviceId || data.g3dExterior) {
            targets.push(object)
            break
          }
        }
      })

      for (const hit of raycaster.intersectObjects(targets, false)) {
        for (let parent: THREE.Object3D | null = hit.object; parent; parent = parent.parent) {
          const data = parent.userData as PickData
          const bedId = data.g3dBedId ?? data.g3dBedIds?.[hit.instanceId ?? -1]
          if (bedId) { onBed(bedId); return }
          if (data.g3dDeviceId) { onDevice(data.g3dDeviceId); return }
          if (data.g3dExterior) { onExterior(); return }
        }
      }
    }

    const pointerDown = (event: PointerEvent) => {
      press = event.button === 0 ? { id: event.pointerId, x: event.clientX, y: event.clientY } : null
    }
    const cancel = () => { press = null }
    canvas.addEventListener('pointerdown', pointerDown)
    canvas.addEventListener('pointerup', pick)
    canvas.addEventListener('pointercancel', cancel)
    return () => {
      canvas.removeEventListener('pointerdown', pointerDown)
      canvas.removeEventListener('pointerup', pick)
      canvas.removeEventListener('pointercancel', cancel)
    }
  }, [gl, camera, scene, onBed, onDevice, onExterior])

  return null
}
