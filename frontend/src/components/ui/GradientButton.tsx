import type { ReactNode } from 'react'

type Props = {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  busy?: boolean
}

export function GradientButton({ children, onClick, disabled, busy }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || busy}
      className="group relative overflow-hidden rounded-xl px-4 py-2.5 font-semibold text-white transition-all duration-300 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="absolute inset-0 bg-gradient-to-r from-saffron via-gold to-violetDeep opacity-95 transition duration-300 group-hover:opacity-100 group-hover:shadow-glow" />
      <span className="absolute inset-y-0 left-0 w-16 -skew-x-12 bg-white/25 blur-md transition-opacity duration-300 group-hover:opacity-100 animate-shimmer" />
      <span className="absolute inset-[1px] rounded-[11px] bg-black/15" />
      <span className="relative z-10 inline-flex items-center gap-2">
        {busy ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/80 border-t-transparent" /> : null}
        {children}
      </span>
    </button>
  )
}
