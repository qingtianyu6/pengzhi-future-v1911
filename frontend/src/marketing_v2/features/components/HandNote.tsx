export default function HandNote({ children, className = '' }: { children: React.ReactNode, className?: string }) {
  return <div className={`hand-note ${className}`}><span>{children}</span><i /></div>
}
