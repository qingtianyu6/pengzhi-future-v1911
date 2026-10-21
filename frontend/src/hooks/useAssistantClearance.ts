import { useEffect } from 'react'

/** Give marked content room when it overlaps the manually positioned companion. */
export function useAssistantClearance(route: string) {
  useEffect(() => {
    let frame = 0, dock: HTMLElement | null = null
    const dockChanges = new MutationObserver(() => schedule())
    const sizeChanges = new ResizeObserver(() => schedule())
    const update = () => {
      frame = 0
      const next = document.querySelector<HTMLElement>('.pengxiaozhi-dock')
      if (dock !== next) {
        dockChanges.disconnect(); sizeChanges.disconnect(); dock = next
        if (dock) {
          dockChanges.observe(dock, { attributes: true, attributeFilter: ['style', 'class'] })
          sizeChanges.observe(dock)
        }
      }
      const occupied = dock?.getBoundingClientRect()
      document.querySelectorAll<HTMLElement>('[data-assistant-clearance]').forEach(element => {
        const box = element.getBoundingClientRect()
        const overlaps = occupied && occupied.width > 0 && occupied.top < box.bottom && occupied.bottom > box.top
          && occupied.left > box.left + box.width * .55 && occupied.left < box.right
        const clearance = overlaps ? Math.ceil(box.right - occupied.left + 12) : 0
        const value = `${clearance}px`
        if (element.style.getPropertyValue('--assistant-clearance') !== value) element.style.setProperty('--assistant-clearance', value)
      })
    }
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(update) }
    const contentChanges = new MutationObserver(schedule)
    contentChanges.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, true)
    schedule()
    return () => {
      window.cancelAnimationFrame(frame)
      contentChanges.disconnect(); dockChanges.disconnect(); sizeChanges.disconnect()
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule, true)
    }
  }, [route])
}
