type Kind = 'tomato'|'strawberry'|'flower'|'seedling'|'base'
export default function CropArtwork({kind}:{kind:Kind}){
  if(kind==='base') return <svg className="crop-art" viewBox="0 0 460 250" role="img" aria-label="规模化温室基地">
    <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#dceef9"/><stop offset="1" stopColor="#eef7ee"/></linearGradient></defs>
    <rect width="460" height="250" fill="url(#sky)"/><path d="M0 100 90 44 178 94 260 36 360 102 460 58v70H0Z" fill="#829b78" opacity=".75"/><path d="M0 126h460v124H0Z" fill="#7ba85f"/>
    {Array.from({length:8}).map((_,i)=><g key={i} transform={`translate(${18+i*54},118)`}><path d="M0 54c4-34 20-48 42-48s38 14 42 48Z" fill="#e9f1ed" stroke="#7d9890" strokeWidth="2"/><path d="M42 6v48M21 14v40M63 14v40" stroke="#a8b7b1"/></g>)}
    <path d="M0 212h460" stroke="#d7e2c3" strokeWidth="9" opacity=".55"/>
  </svg>
  const palette = kind==='tomato'?['#d73f2d','#f46a52']:kind==='strawberry'?['#db3546','#f45a63']:kind==='flower'?['#f49cb0','#ffd5de']:['#6bbf65','#9ad37d']
  return <svg className="crop-art" viewBox="0 0 460 250" role="img" aria-label={`${kind} greenhouse illustration`}>
    <defs><linearGradient id={`g-${kind}`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#dff1f2"/><stop offset=".54" stopColor="#f7fbf7"/><stop offset="1" stopColor="#d9ead1"/></linearGradient></defs>
    <rect width="460" height="250" fill={`url(#g-${kind})`}/><path d="M25 215V70C25 34 61 16 100 16h260c39 0 75 18 75 54v145" fill="none" stroke="#90a8a1" strokeWidth="5" opacity=".7"/>
    {[70,140,210,280,350,420].map(x=><path key={x} d={`M${x} 30v185`} stroke="#c1d1cb" strokeWidth="2"/>)}<path d="M25 92h410M25 145h410" stroke="#cfdbd6" strokeWidth="2"/>
    {kind==='tomato' && Array.from({length:13}).map((_,i)=>{const x=30+(i%7)*64,y=120+Math.floor(i/7)*54;return <g key={i}><path d={`M${x+18} ${y-35}c8 20 3 42-9 60`} stroke="#318352" strokeWidth="5" fill="none"/><circle cx={x+16} cy={y} r="13" fill={palette[i%2]}/><circle cx={x+38} cy={y+12} r="11" fill={palette[(i+1)%2]}/><path d={`M${x+16} ${y-13}l-8-6m8 6 8-7`} stroke="#2b7c45" strokeWidth="3"/></g>})}
    {kind==='strawberry' && Array.from({length:18}).map((_,i)=>{const x=26+(i%9)*48,y=122+Math.floor(i/9)*55;return <g key={i}><path d={`M${x+10} ${y-30}q10 12 1 30`} stroke="#398e50" strokeWidth="4" fill="none"/><path d={`M${x} ${y}q10-14 20 0-1 21-10 30Q1 ${y+21} ${x} ${y}Z`} fill={palette[i%2]}/><path d={`M${x+2} ${y+2}l8-8 8 8`} stroke="#2c8242" strokeWidth="3" fill="none"/></g>})}
    {kind==='flower' && Array.from({length:23}).map((_,i)=>{const x=18+(i%10)*45,y=112+Math.floor(i/10)*45;return <g key={i}><path d={`M${x+13} ${y+14}v22`} stroke="#4c9660" strokeWidth="4"/><g transform={`translate(${x+13} ${y+13})`}>{[0,72,144,216,288].map(a=><ellipse key={a} rx="6" ry="13" fill={palette[i%2]} transform={`rotate(${a}) translate(0 -8)`}/>)}<circle r="6" fill="#f1c253"/></g></g>})}
    {kind==='seedling' && <>{Array.from({length:8}).map((_,r)=>Array.from({length:14}).map((_,c)=>{const x=16+c*32,y=100+r*18;return <g key={`${r}-${c}`}><rect x={x} y={y} width="20" height="12" rx="2" fill="#263f2f"/><path d={`M${x+10} ${y+5}c-8-12-13-3-9 4 5 5 9 4 9 4m0-4c8-12 13-3 9 4-5 5-9 4-9 4`} stroke={palette[0]} strokeWidth="2.3" fill="none"/></g>}))}</>}
  </svg>
}
