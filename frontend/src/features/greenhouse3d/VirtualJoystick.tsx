import { DownOutlined, LeftOutlined, RightOutlined, UpOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useRef, useState, type PointerEvent, type RefObject } from 'react'
import type { MovementInput, WalkPosition } from './scene/controls/FirstPersonController'

export default function VirtualJoystick({ inputRef, positionRef }: { inputRef: RefObject<MovementInput>; positionRef: RefObject<WalkPosition> }) {
  const pointerId = useRef<number | null>(null)
  const [vector, setVector] = useState<MovementInput>({ x: 0, y: 0 })
  const [walkPosition, setWalkPosition] = useState<WalkPosition>(() => ({ ...positionRef.current }))

  const reset = useCallback(() => {
    pointerId.current = null
    inputRef.current.x = 0
    inputRef.current.y = 0
    setVector({ x: 0, y: 0 })
  }, [inputRef])

  useEffect(() => {
    const input = inputRef.current
    window.addEventListener('blur', reset)
    return () => {
      window.removeEventListener('blur', reset)
      input.x = 0
      input.y = 0
    }
  }, [inputRef, reset])

  useEffect(() => {
    const timer = window.setInterval(() => {
      const next = positionRef.current
      setWalkPosition((current) => Math.abs(current.x - next.x) >= .05 || Math.abs(current.z - next.z) >= .05 || current.facing !== next.facing
        ? { x: next.x, z: next.z, facing: next.facing } : current)
    }, 250)
    return () => window.clearInterval(timer)
  }, [positionRef])

  const update = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const radius = rect.width * 0.34
    const x = (event.clientX - rect.left - rect.width / 2) / radius
    const y = (event.clientY - rect.top - rect.height / 2) / radius
    const length = Math.max(1, Math.hypot(x, y))
    const next = { x: x / length, y: y / length }
    inputRef.current.x = next.x
    inputRef.current.y = next.y
    setVector(next)
  }

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (pointerId.current !== null || (event.pointerType === 'mouse' && event.button !== 0)) return
    pointerId.current = event.pointerId
    event.currentTarget.setPointerCapture(event.pointerId)
    update(event)
  }

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (pointerId.current === event.pointerId) update(event)
  }

  const onPointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (pointerId.current !== event.pointerId) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    reset()
  }

  return <div className="g3d-joystick" role="group" aria-label="漫游移动转盘"
    data-walk-x={walkPosition.x.toFixed(2)} data-walk-z={walkPosition.z.toFixed(2)}
    onPointerDown={onPointerDown} onPointerMove={onPointerMove}
    onPointerUp={onPointerEnd} onPointerCancel={onPointerEnd}
    onLostPointerCapture={reset} onContextMenu={(event) => event.preventDefault()}>
    <span className="g3d-joystick-location">距入口 {Math.max(0, 16 - walkPosition.x).toFixed(1)} m · 朝向{walkPosition.facing}</span>
    <span className="g3d-joystick-direction up"><UpOutlined /></span>
    <span className="g3d-joystick-direction right"><RightOutlined /></span>
    <span className="g3d-joystick-direction down"><DownOutlined /></span>
    <span className="g3d-joystick-direction left"><LeftOutlined /></span>
    <span className="g3d-joystick-thumb" style={{ left: `${50 + vector.x * 31}%`, top: `${50 + vector.y * 31}%` }} />
  </div>
}
