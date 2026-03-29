type Props = {
  type: 'error' | 'success' | 'info'
  message: string
  onClose: () => void
}

export function Toast({ type, message, onClose }: Props) {
  const color =
    type === 'error'
      ? 'border-red-400/50 bg-red-500/15 text-red-200'
      : type === 'success'
      ? 'border-emerald-400/40 bg-emerald-500/15 text-emerald-200'
      : 'border-indigo-400/40 bg-indigo-500/15 text-indigo-100'

  return (
    <div className={`fixed bottom-5 right-5 z-50 max-w-md rounded-xl border px-4 py-3 shadow-soft ${color}`}>
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm">{message}</p>
        <button className="text-xs opacity-80 hover:opacity-100" onClick={onClose}>
          ✕
        </button>
      </div>
    </div>
  )
}
