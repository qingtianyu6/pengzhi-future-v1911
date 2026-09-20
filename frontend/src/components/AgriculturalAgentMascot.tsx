export function AgriculturalAgentMascot({ compact = false }: { compact?: boolean }) {
  return <div className={`agent-mascot${compact ? ' compact' : ''}`} aria-hidden="true">
    <svg viewBox="0 0 120 140" role="img">
      <defs>
        <linearGradient id="hat" x1="0" x2="1">
          <stop offset="0" stopColor="#f0b84a" />
          <stop offset="1" stopColor="#ffd878" />
        </linearGradient>
        <linearGradient id="shirt" x1="0" x2="1">
          <stop offset="0" stopColor="#0f6d52" />
          <stop offset="1" stopColor="#1ea377" />
        </linearGradient>
      </defs>
      <path d="M42 28c8-16 28-20 43-8 8 6 11 15 10 24H30c0-5 4-11 12-16Z" fill="url(#hat)" />
      <path d="M24 43c11-5 25-7 39-7 18 0 33 3 43 9-6 7-20 10-42 10-20 0-33-4-40-12Z" fill="#e4a736" />
      <path d="M79 18c6-8 15-10 23-8-1 9-7 16-18 18" fill="#53b45b" />
      <path d="M84 20c4 0 8 2 12 6" fill="none" stroke="#2d8746" strokeWidth="3" strokeLinecap="round" />
      <rect x="32" y="47" width="64" height="58" rx="27" fill="#f4cda6" />
      <circle cx="53" cy="72" r="4" fill="#183c31" />
      <circle cx="76" cy="72" r="4" fill="#183c31" />
      <path d="M55 88c6 5 13 5 19 0" fill="none" stroke="#a6604b" strokeWidth="3" strokeLinecap="round" />
      <path d="M20 137c1-22 14-35 40-35s40 13 41 35" fill="url(#shirt)" />
      <path d="M51 104l9 13 9-13" fill="#f5dfb7" />
      <circle cx="91" cy="109" r="13" fill="#f5bf4f" />
      <path d="M91 101v16M83 109h16" stroke="#fff8df" strokeWidth="3" strokeLinecap="round" />
      <path d="M29 116c-8 4-12 11-14 21M94 119c8 3 12 9 14 18" fill="none" stroke="#176e55" strokeWidth="9" strokeLinecap="round" />
    </svg>
  </div>
}
