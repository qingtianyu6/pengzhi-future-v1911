import { useEffect, useState, type RefObject } from 'react'

type Point = { right: number; bottom: number }
type Box = { left: number; top: number; right: number; bottom: number }
const overlap = (a: Box, b: Box) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top))

/** Choose a free viewport location without changing the user's saved drag position. */
export function useAssistantPlacement(ref: RefObject<HTMLDivElement | null>, preferred: Point, active: boolean, context: string) {
  const [point, setPoint] = useState<Point>(preferred)
  useEffect(() => {
    if (!active) return
    let timer = 0
    let disposed = false
    const place = () => {
      if (disposed || !ref.current || ref.current.matches(':hover, :focus-within')) return
      const dock = ref.current.getBoundingClientRect()
      const scope = document.querySelector('#pengzhi-platform .exact-main-layout') ?? document.querySelector('main') ?? document.body
      const bounds = scope.getBoundingClientRect()
      const left = Math.max(12, bounds.left + 12)
      const right = Math.max(left, innerWidth - dock.width - 12)
      const top = 90
      const bottom = Math.max(top, innerHeight - dock.height - 16)
      const controls: Box[] = [], text: Box[] = []
      scope.querySelectorAll('button,a,input,textarea,select,[role="combobox"],summary,h1,h2,h3,p,label,.g3d-telemetry,.g3d-warning').forEach(element => {
        if (element.closest('.pengxiaozhi-dock,[aria-hidden="true"],.ant-select-dropdown,.ant-menu-sub')) return
        const rect = element.getBoundingClientRect()
        if (!rect.width || !rect.height || rect.bottom < top || rect.top > innerHeight || rect.right < left || getComputedStyle(element).visibility === 'hidden') return
        const box = { left: rect.left - 6, top: rect.top - 6, right: rect.right + 6, bottom: rect.bottom + 6 }
        if (element.matches('button,a,input,textarea,select,[role="combobox"],summary')) controls.push(box)
        else text.push(box)
      })
      const preferredX = Math.max(left, Math.min(right, innerWidth - preferred.right - dock.width))
      const preferredY = Math.max(top, Math.min(bottom, innerHeight - preferred.bottom - dock.height))
      const xs = [preferredX, right, left, (left + right) / 2]
      const ys = [preferredY, bottom, top]
      for (let y = top; y < bottom; y += 36) ys.push(y)
      let best = { x: preferredX, y: preferredY, score: Infinity }
      for (const x of xs) for (const y of ys) {
        const box = { left: x, top: y, right: x + dock.width, bottom: y + dock.height }
        // Any control overlap outranks text and distance; scores are layout costs only.
        const cost = controls.reduce((n, b) => n + (overlap(box, b) > 0 ? 1e8 + overlap(box, b) * 100 : 0), 0)
          + text.reduce((n, b) => n + overlap(box, b), 0)
          + Math.hypot(x - preferredX, y - preferredY) * 4
        if (cost < best.score) best = { x, y, score: cost }
      }
      const next = { right: Math.round(innerWidth - best.x - dock.width), bottom: Math.round(innerHeight - best.y - dock.height) }
      setPoint(previous => previous.right === next.right && previous.bottom === next.bottom ? previous : next)
    }
    const schedule = () => { window.clearTimeout(timer); timer = window.setTimeout(place, 120) }
    const observer = new MutationObserver(schedule)
    const scope = document.querySelector('.pz-workspace-page') ?? document.querySelector('main')
    if (scope) observer.observe(scope, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-expanded', 'class'] })
    window.addEventListener('scroll', schedule, true)
    window.addEventListener('resize', schedule)
    document.addEventListener('load', schedule, true)
    void document.fonts.ready.then(schedule)
    schedule()
    return () => {
      disposed = true; window.clearTimeout(timer); observer.disconnect()
      window.removeEventListener('scroll', schedule, true); window.removeEventListener('resize', schedule)
      document.removeEventListener('load', schedule, true)
    }
  }, [ref, preferred.right, preferred.bottom, active, context])
  return active ? point : preferred
}
