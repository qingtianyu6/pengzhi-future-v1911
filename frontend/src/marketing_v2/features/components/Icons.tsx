export function SearchIcon() {
  return <svg viewBox="0 0 24 24" className="line-icon"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>
}
export function UserIcon() {
  return <svg viewBox="0 0 24 24" className="line-icon"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 19c.8-4.2 3-6 6.5-6s5.7 1.8 6.5 6"/></svg>
}
export function LeafIcon() {
  return <svg viewBox="0 0 28 28" className="leaf-icon"><path d="M23 5C14 5 6 9 5 18c4 1 8 0 11-3-3 4-6 6-10 7 5 2 11 0 14-5 2-4 3-8 3-12Z" fill="currentColor"/><path d="M6 22c4-6 8-9 14-12" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/></svg>
}

export function RecordGlyph({ kind }: { kind: string }) {
  const base = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  if (kind === 'water') return <svg viewBox="0 0 28 28" className="record-glyph"><path d="M14 4c4 5 6 8 6 11a6 6 0 1 1-12 0c0-3 2-6 6-11Z" {...base}/><path d="M8 22h12" {...base}/></svg>
  if (kind === 'fertilize') return <svg viewBox="0 0 28 28" className="record-glyph"><rect x="7" y="5" width="14" height="18" rx="2.5" {...base}/><path d="M10 9h8M10 13h5M10 17h7" {...base}/></svg>
  if (kind === 'spray') return <svg viewBox="0 0 28 28" className="record-glyph"><path d="M10 10h8v13h-8zM12 7h4M15 7l3-3M18 4h4" {...base}/><path d="M21 7h3M20 10l3 1" {...base}/></svg>
  if (kind === 'patrol') return <svg viewBox="0 0 28 28" className="record-glyph"><path d="M7 5h12l2 3v15H7z" {...base}/><path d="M10 10h8M10 14h6M10 18h5" {...base}/></svg>
  return <svg viewBox="0 0 28 28" className="record-glyph"><rect x="7" y="5" width="14" height="18" rx="2" {...base}/><path d="M10 9h8M10 13h8M10 17h5" {...base}/></svg>
}
