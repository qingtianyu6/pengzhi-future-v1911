export default function Brand() {
  return (
    <div className="brand" aria-label="棚智未来">
      <svg className="brand__mark" viewBox="0 0 66 66" aria-hidden="true">
        <path d="M33 5 54 17v24L33 60 12 41V17L33 5Z" fill="none" stroke="currentColor" strokeWidth="3.2" />
        <path d="M17 45c10-2 18-8 22-21 5 10 4 20-3 28" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" />
        <path d="M21 46c8 2 17 2 25-1" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
        <path d="M37 20c-7 1-13 5-17 12 6 2 13 0 19-6" fill="currentColor" opacity=".16" />
      </svg>
      <div className="brand__text">
        <strong>棚智未来</strong>
        <span>让农业更有未来</span>
      </div>
    </div>
  )
}
