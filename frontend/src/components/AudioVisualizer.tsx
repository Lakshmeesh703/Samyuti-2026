type Props = {
  active: boolean
}

export function AudioVisualizer({ active }: Props) {
  return (
    <div className="flex h-12 items-end justify-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2">
      {Array.from({ length: 20 }).map((_, i) => (
        <span
          key={i}
          className={`wave-bar h-full w-1 rounded-full bg-gradient-to-t from-violetDeep via-saffron to-gold ${active ? 'animate-bars' : 'opacity-40'}`}
          style={{ animationDelay: `${i * 80}ms` }}
        />
      ))}
    </div>
  )
}
