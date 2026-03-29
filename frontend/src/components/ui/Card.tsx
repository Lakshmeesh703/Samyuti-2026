import type { ReactNode } from 'react'

type Props = {
  title?: string
  subtitle?: string
  children: ReactNode
  className?: string
}

export function Card({ title, subtitle, children, className = '' }: Props) {
  return (
    <section className={`glass-card animate-fadeUp rounded-2xl p-5 hover:-translate-y-0.5 hover:border-white/20 ${className}`}>
      {title ? <h3 className="text-lg font-semibold text-slate-100">{title}</h3> : null}
      {subtitle ? <p className="mb-4 mt-1 text-sm text-slate-300/90">{subtitle}</p> : null}
      {children}
    </section>
  )
}
