import type { ReactNode, SVGProps } from 'react'

type IconName =
  | 'leaf' | 'sprout' | 'grid' | 'search' | 'user' | 'layers' | 'bell'
  | 'document' | 'chart' | 'alert' | 'decision' | 'plane' | 'database'
  | 'sensor' | 'bug' | 'farm' | 'assistant' | 'check' | 'phone'

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  let body: ReactNode
  switch (name) {
    case 'leaf': body = <><path {...common} d="M18 5C11 6 6 10 5 18c7 1 12-2 14-9"/><path {...common} d="M6 19c4-5 8-8 13-10"/></>; break
    case 'sprout': body = <><path {...common} d="M12 21v-8"/><path {...common} d="M12 14c-5 0-8-3-8-7 5 0 8 2 8 7Z"/><path {...common} d="M12 12c4 0 7-2 8-6-5 0-8 2-8 6Z"/><path {...common} d="M5 21h14"/></>; break
    case 'grid': body = <><rect {...common} x="4" y="4" width="6" height="6" rx="1"/><rect {...common} x="14" y="4" width="6" height="6" rx="1"/><rect {...common} x="4" y="14" width="6" height="6" rx="1"/><rect {...common} x="14" y="14" width="6" height="6" rx="1"/></>; break
    case 'search': body = <><circle {...common} cx="11" cy="11" r="6"/><path {...common} d="m16 16 4 4"/></>; break
    case 'user': body = <><circle {...common} cx="12" cy="8" r="3"/><path {...common} d="M5 20c.8-4 3-6 7-6s6.2 2 7 6"/></>; break
    case 'layers': body = <><path {...common} d="m12 4 8 4-8 4-8-4 8-4Z"/><path {...common} d="m4 12 8 4 8-4"/><path {...common} d="m4 16 8 4 8-4"/></>; break
    case 'bell': body = <><path {...common} d="M6 16h12l-1.5-2.5V10a4.5 4.5 0 0 0-9 0v3.5L6 16Z"/><path {...common} d="M10 19a2.2 2.2 0 0 0 4 0"/></>; break
    case 'document': body = <><path {...common} d="M7 3h7l4 4v14H7z"/><path {...common} d="M14 3v5h5"/><path {...common} d="M10 12h5M10 16h5"/></>; break
    case 'chart': body = <><path {...common} d="M5 20V9M12 20V4M19 20v-7"/><path {...common} d="M3 20h18"/></>; break
    case 'alert': body = <><path {...common} d="M12 3c4 0 7 3.2 7 7.2V15l2 2H3l2-2v-4.8C5 6.2 8 3 12 3Z"/><path {...common} d="M10 20h4"/><path {...common} d="M12 8v3M12 14h.01"/></>; break
    case 'decision': body = <><rect {...common} x="5" y="4" width="14" height="16" rx="2"/><path {...common} d="M8 9h8M8 13h5M8 17h7"/><path {...common} d="m15 13 2 2 3-4"/></>; break
    case 'plane': body = <><path {...common} d="m21 4-8 17-2-7-7-2 17-8Z"/><path {...common} d="m11 14 5-5"/></>; break
    case 'database': body = <><ellipse {...common} cx="12" cy="5.5" rx="7" ry="3"/><path {...common} d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/><path {...common} d="M5 11.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></>; break
    case 'sensor': body = <><rect {...common} x="7" y="8" width="10" height="11" rx="2"/><path {...common} d="M12 8V4M5 5l2 2M19 5l-2 2M10 12h4M10 15h4"/></>; break
    case 'bug': body = <><ellipse {...common} cx="12" cy="13" rx="5" ry="6"/><path {...common} d="M9 6c0-2 1-3 3-3s3 1 3 3M7 10 4 8M7 14H3M17 10l3-2M17 14h4M8 18l-3 2M16 18l3 2"/><path {...common} d="M12 7v12"/></>; break
    case 'farm': body = <><path {...common} d="M5 19h14M7 19v-8h10v8"/><path {...common} d="m7 11 5-4 5 4"/><path {...common} d="M12 7V4"/></>; break
    case 'assistant': body = <><rect {...common} x="4" y="5" width="16" height="13" rx="3"/><circle cx="9" cy="11" r="1" fill="currentColor"/><circle cx="15" cy="11" r="1" fill="currentColor"/><path {...common} d="M9 15h6M12 5V2"/></>; break
    case 'check': body = <><circle {...common} cx="12" cy="12" r="9"/><path {...common} d="m8 12 3 3 5-6"/></>; break
    case 'phone': body = <><rect {...common} x="7" y="2.5" width="10" height="19" rx="2.3"/><path {...common} d="M10 5h4M11 19h2"/></>; break
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>{body}</svg>
}
