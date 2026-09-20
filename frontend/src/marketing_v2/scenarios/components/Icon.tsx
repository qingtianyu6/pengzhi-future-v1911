import type { ReactElement } from 'react'

const paths: Record<string, ReactElement> = {
 search:<><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
 user:<><circle cx="12" cy="8" r="4"/><path d="M4 21c1-5 4-7 8-7s7 2 8 7"/></>,
 pin:<><path d="M12 22s7-6 7-13a7 7 0 1 0-14 0c0 7 7 13 7 13Z"/><circle cx="12" cy="9" r="2"/></>,
 settings:<><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1-2-4-2 1a7 7 0 0 0-2-1l-.4-2h-5L9 6a7 7 0 0 0-2 1L5 6 3 10l2 1a7 7 0 0 0 0 2l-2 1 2 4 2-1a7 7 0 0 0 2 1l.5 2h5l.5-2a7 7 0 0 0 2-1l2 1 2-4-2-1a7 7 0 0 0 .1-1Z"/></>,
 trend:<><path d="M4 19V9M10 19V5M16 19v-8M22 19V3"/><path d="m3 12 6-5 5 3 7-7"/></>,
 users:<><circle cx="9" cy="9" r="3"/><circle cx="17" cy="8" r="2.5"/><path d="M3 20c.5-4 2.5-6 6-6s5.5 2 6 6M14 14c3 0 5 2 5.5 5"/></>,
 activity:<><path d="M3 12h4l2-5 4 10 2-5h6"/></>,
 camera:<><path d="M4 7h4l2-2h4l2 2h4v12H4Z"/><circle cx="12" cy="13" r="4"/></>,
 clipboard:<><rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 5V3h6v2M8 10h8M8 14h8M8 18h5"/></>,
 shield:<><path d="M12 3 20 6v6c0 5-3 8-8 10-5-2-8-5-8-10V6Z"/><path d="m9 12 2 2 4-4"/></>,
 sliders:<><path d="M4 7h16M4 17h16M8 4v6M16 14v6"/></>,
 sprout:<><path d="M12 21v-8M12 13c-5 0-7-3-7-7 5 0 7 3 7 7ZM12 15c5 0 7-3 7-7-5 0-7 3-7 7Z"/></>,
 database:<><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 2 4 3 8 3s8-1 8-3V5M4 11v6c0 2 4 3 8 3s8-1 8-3v-6"/></>
}
export default function Icon({name,className}:{name:string,className?:string}){return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]||paths.activity}</svg>}
