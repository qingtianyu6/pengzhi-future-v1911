import { useEffect, useRef, useState } from 'react'

export type CompanionMotion = 'idle' | 'blink' | 'wave' | 'stretch' | 'sitting' | 'dozing'

const restCycle: { motion: CompanionMotion; duration: number; hint?: string }[] = [
  { motion: 'idle', duration: 6500 },
  { motion: 'blink', duration: 180 },
  { motion: 'idle', duration: 6200 },
  { motion: 'stretch', duration: 2400, hint: '伸个懒腰，继续陪你看棚。' },
  { motion: 'idle', duration: 6800 },
  { motion: 'sitting', duration: 9000, hint: '我坐一会儿，有事随时叫我。' },
  { motion: 'dozing', duration: 11000 },
  { motion: 'sitting', duration: 2200 },
]

/** A quiet, cancellable companion loop. It never sends chat requests or starts audio. */
export function useMascotCompanion(active: boolean, enabled: boolean, contextKey: string) {
  const [motion, setMotion] = useState<CompanionMotion>('idle')
  const [hint, setHint] = useState<string | null>(null)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.classList.contains('pengzhi-reduced-motion'))
  const [resting, setRestingState] = useState(false)
  const commandAt = useRef(-Infinity)
  const interacting = hovered || focused

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReducedMotion(preference.matches || Boolean(document.querySelector('.pengzhi-reduced-motion')))
    const observer = new MutationObserver(update)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] })
    preference.addEventListener('change', update)
    update()
    return () => { preference.removeEventListener('change', update); observer.disconnect() }
  }, [])

  useEffect(() => {
    setMotion('idle')
    setHint(null)
    if (!active) { setHovered(false); setFocused(false) }
    if (!active || !enabled || reducedMotion) return
    let timer = 0
    let hintTimer = 0
    const showHint = (text?: string) => {
      window.clearTimeout(hintTimer)
      setHint(text ?? null)
      if (text) hintTimer = window.setTimeout(() => setHint(null), 3800)
    }
    if (interacting) {
      setMotion('wave')
      showHint('嗨，我在！点我聊聊大棚里的事。')
      timer = window.setTimeout(() => setMotion('idle'), 1800)
    } else if (resting) {
      setMotion('sitting')
      showHint('我坐一会儿，有事随时叫我。')
      timer = window.setTimeout(() => setMotion('dozing'), 9000)
    } else {
      const step = (index: number) => {
        const current = restCycle[index]
        setMotion(current.motion)
        showHint(current.hint)
        timer = window.setTimeout(() => step((index + 1) % restCycle.length), current.duration)
      }
      step(0)
    }
    return () => { window.clearTimeout(timer); window.clearTimeout(hintTimer) }
  }, [active, enabled, reducedMotion, interacting, contextKey, resting])

  const respondToPointer = (pointerType: string) => { if (pointerType !== 'touch' && performance.now() - commandAt.current > 600) setHovered(true) }
  return { motion, hint, resting, setResting: (next: boolean) => {
      commandAt.current = performance.now(); setHovered(false); setFocused(false); setRestingState(next)
    }, quiet: !enabled || reducedMotion,
    onPointerEnter: respondToPointer,
    onPointerMove: respondToPointer,
    onPointerLeave: () => setHovered(false),
    onFocus: () => { if (performance.now() - commandAt.current > 600) setFocused(true) },
    onBlur: () => setFocused(false),
  }
}
