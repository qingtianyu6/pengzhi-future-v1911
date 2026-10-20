export function LeafOutlined(){return <svg className="iw-leaf-symbol" viewBox="0 0 28 30" fill="none" aria-hidden="true"><path d="M6 24C-1 9 11 8 23 3c1 11-1 23-15 22M5 29 19 9M12 20l-1-8M12 20l8-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M10 23C5 13 12 10 20 7c-2 7-5 13-10 16Z" fill="currentColor" opacity=".18"/></svg>}

export function InvestigationNavIcon({name}:{name:string}){
  const paths:Record<string,string>={
    overview:'M2 11 12 2l10 9M5 9v13h5v-8h5v8h5V9',
    greenhouse:'M3 10 12 3l9 7v12H3ZM3 10h18M8 10v12M16 10v12M8 15h8',
    'digital-twin':'M2 7 12 2l10 5v12l-10 5-10-5ZM2 7l10 5 10-5M12 12v12',
    environment:'M3 14h4v10H3ZM10 7h4v17h-4ZM17 2h4v22h-4Z',
    diagnosis:'M4 21C0 7 13 10 23 3c0 11-4 20-16 18M3 25 17 10M9 18l-1-6M9 18l8-1',
    production:'M8 4H4v20h17V4h-5M8 2h8v5H8ZM8 12h9M8 17h9',
    knowledge:'M12 5C8 2 4 2 1 3v19c4-1 8-1 11 2M12 5c4-3 8-3 11-2v19c-4-1-8-1-11 2ZM12 5v19',
  }
  return <svg className="iw-nav-symbol" viewBox="0 0 26 28" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.overview}/></svg>
}
