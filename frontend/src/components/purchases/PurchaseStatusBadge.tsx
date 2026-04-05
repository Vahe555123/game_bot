import clsx from 'clsx'

const STATUS_CLASSES: Record<string, string> = {
  payment_pending: 'border-amber-300/20 bg-amber-500/12 text-amber-50',
  payment_review: 'border-sky-300/20 bg-sky-500/12 text-sky-50',
  fulfilled: 'border-emerald-400/20 bg-emerald-500/12 text-emerald-100',
  cancelled: 'border-rose-400/20 bg-rose-500/12 text-rose-100',
}

export function PurchaseStatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span className={clsx('pill', STATUS_CLASSES[status] || 'bg-white/5 text-slate-200')}>
      {label}
    </span>
  )
}
