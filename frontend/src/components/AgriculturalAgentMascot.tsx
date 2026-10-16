import type { CompanionMotion } from '../hooks/useMascotCompanion'

export type MascotState = 'idle' | 'greeting' | 'thinking' | 'reminder' | 'complete' | 'unavailable' | 'listening' | 'speaking'

const companionPositions: Record<CompanionMotion, string> = { idle: '0 0', blink: '50% 0', wave: '100% 0', stretch: '0 100%', sitting: '50% 100%', dozing: '100% 100%' }

export function AgriculturalAgentMascot({ compact = false, state = 'idle', showStateBadge = true, motion }: { compact?: boolean; state?: MascotState; showStateBadge?: boolean; motion?: CompanionMotion }) {
  const position = state === 'thinking' ? '100% 0' : state === 'reminder' ? '0 100%' : state === 'complete' ? '100% 100%' : '0 0'
  return <span className={`agent-mascot pengxiaozhi-mascot${compact ? ' compact' : ''} mascot-${state}`} aria-hidden="true">
    {motion && state === 'idle' ? <span className="mascot-sprite mascot-companion-sprite" style={{ backgroundPosition: companionPositions[motion] }} /> : compact || state === 'greeting' ? <img src="/assistant/pengxiaozhi.png" alt="" draggable={false} decoding="async" /> : <span className="mascot-sprite" style={{ backgroundPosition: position }} />}
    {state === 'thinking' && <span className="mascot-state-dots"><i /><i /><i /></span>}
    {showStateBadge && state === 'complete' && <span className="mascot-state-badge">✓</span>}
    {showStateBadge && state === 'reminder' && <span className="mascot-state-badge is-warning">!</span>}
    {(state === 'listening' || state === 'speaking') && <span className="mascot-voice-bars"><i /><i /><i /><i /></span>}
  </span>
}
