import { PointerLockControls } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useRef, type RefObject } from 'react'
import * as THREE from 'three'
import type { Collider } from '../config/types'
import { canMoveTo } from './CollisionController'

export type MovementInput = { x: number; y: number }
export type FacingDirection = '棚内' | '入口' | 'A/C区' | 'B/D区'
export type WalkPosition = { x: number; z: number; facing: FacingDirection }
export type ViewStop = 'entrance' | 'A' | 'B' | 'C' | 'D'
export type ViewPoint = { position: [number, number, number]; target: [number, number, number] }

export default function FirstPersonController({ enabled, colliders, spawn, movement, position, navigation, viewPoints }: { enabled: boolean; colliders: Collider[]; spawn: [number, number, number]; movement: RefObject<MovementInput>; position: RefObject<WalkPosition>; navigation: RefObject<ViewStop | null>; viewPoints: Record<ViewStop, ViewPoint> }) {
  const { camera, gl } = useThree()
  const keys = useRef<Record<string, boolean>>({})
  const drag = useRef<{ id: number; x: number; y: number; startX: number; startY: number; active: boolean; pointerType: string } | null>(null)
  const facingVector = useRef(new THREE.Vector3())

  useEffect(() => {
    if (!enabled) return
    camera.position.set(...spawn)
    position.current.x = spawn[0]
    position.current.z = spawn[2]
    camera.rotation.reorder('YXZ')
    const down = (event: KeyboardEvent) => { keys.current[event.code] = true }
    const up = (event: KeyboardEvent) => { keys.current[event.code] = false }
    const blur = () => { keys.current = {}; drag.current = null }
    const pointerDown = (event: globalThis.PointerEvent) => {
      if (document.pointerLockElement || (event.pointerType !== 'touch' && event.button !== 0 && event.button !== 2)) return
      const active = event.pointerType === 'touch' || event.button === 2
      drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, active, pointerType: event.pointerType }
      if (active) gl.domElement.setPointerCapture(event.pointerId)
    }
    const pointerMove = (event: globalThis.PointerEvent) => {
      const current = drag.current
      if (current?.id !== event.pointerId) return
      if (!current.active) {
        if (Math.hypot(event.clientX - current.startX, event.clientY - current.startY) < 5) return
        current.active = true
        gl.domElement.setPointerCapture(event.pointerId)
      }
      const sensitivity = current.pointerType === 'mouse' ? .005 : .0035
      camera.rotation.y -= (event.clientX - current.x) * sensitivity
      camera.rotation.x = THREE.MathUtils.clamp(camera.rotation.x - (event.clientY - current.y) * sensitivity, -1.25, 1.25)
      current.x = event.clientX
      current.y = event.clientY
    }
    const pointerUp = (event: globalThis.PointerEvent) => {
      if (drag.current?.id !== event.pointerId) return
      drag.current = null
      if (gl.domElement.hasPointerCapture(event.pointerId)) gl.domElement.releasePointerCapture(event.pointerId)
    }
    const contextMenu = (event: MouseEvent) => event.preventDefault()
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    gl.domElement.addEventListener('pointerdown', pointerDown)
    gl.domElement.addEventListener('pointermove', pointerMove)
    gl.domElement.addEventListener('pointerup', pointerUp)
    gl.domElement.addEventListener('pointercancel', pointerUp)
    gl.domElement.addEventListener('lostpointercapture', pointerUp)
    gl.domElement.addEventListener('contextmenu', contextMenu)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('blur', blur)
      gl.domElement.removeEventListener('pointerdown', pointerDown)
      gl.domElement.removeEventListener('pointermove', pointerMove)
      gl.domElement.removeEventListener('pointerup', pointerUp)
      gl.domElement.removeEventListener('pointercancel', pointerUp)
      gl.domElement.removeEventListener('lostpointercapture', pointerUp)
      gl.domElement.removeEventListener('contextmenu', contextMenu)
    }
  }, [enabled, camera, gl, spawn, position])

  useFrame((_, dt) => {
    if (!enabled) return
    if (navigation.current) {
      const view = viewPoints[navigation.current]
      navigation.current = null
      camera.position.set(...view.position)
      camera.lookAt(...view.target)
      camera.rotation.reorder('YXZ')
      position.current.x = camera.position.x
      position.current.z = camera.position.z
    }
    camera.getWorldDirection(facingVector.current)
    const forward = facingVector.current
    position.current.facing = Math.abs(forward.x) >= Math.abs(forward.z)
      ? (forward.x < 0 ? '棚内' : '入口')
      : (forward.z > 0 ? 'A/C区' : 'B/D区')
    const direction = new THREE.Vector3(movement.current.x, 0, movement.current.y)
    if (keys.current.KeyW) direction.z -= 1
    if (keys.current.KeyS) direction.z += 1
    if (keys.current.KeyA) direction.x -= 1
    if (keys.current.KeyD) direction.x += 1
    const strength = Math.min(1, direction.length())
    if (!strength) return
    direction.normalize().applyQuaternion(camera.quaternion)
    direction.y = 0
    direction.normalize()
    const distance = strength * (keys.current.ShiftLeft ? 4.2 : 2.8) * Math.min(dt, .2)
    const segments = Math.max(1, Math.ceil(distance / .18))
    const step = direction.multiplyScalar(distance / segments)
    for (let index = 0; index < segments; index += 1) {
      const next = camera.position.clone().add(step)
      next.y = spawn[1]
      if (canMoveTo(next, colliders)) {
        camera.position.copy(next)
      } else {
        const alongX = camera.position.clone().add(new THREE.Vector3(step.x, 0, 0))
        const alongZ = camera.position.clone().add(new THREE.Vector3(0, 0, step.z))
        if (canMoveTo(alongX, colliders)) camera.position.copy(alongX)
        if (canMoveTo(alongZ, colliders)) camera.position.copy(alongZ)
      }
    }
    position.current.x = camera.position.x
    position.current.z = camera.position.z
  })

  // Lock the pointer only on explicit request so ordinary scene clicks can inspect beds and devices.
  return enabled ? <PointerLockControls selector=".g3d-lock-control" /> : null
}
