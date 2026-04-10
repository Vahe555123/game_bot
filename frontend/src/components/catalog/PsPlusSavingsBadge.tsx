import clsx from 'clsx'

type PsPlusSavingsBadgeProps = {
  percent: number
  className?: string
}

export function PsPlusSavingsBadge({ percent, className }: PsPlusSavingsBadgeProps) {
  if (!Number.isFinite(percent) || percent <= 0) {
    return null
  }

  return (
    <span
      className={clsx(
        'pill border-[#f4b526] bg-gradient-to-r from-[#ffd54a] to-[#f5a623] px-3 py-1.5 text-[11px] font-bold tracking-normal text-slate-950 shadow-lg shadow-amber-950/20',
        className,
      )}
    >
      <img src="/static/images/psplussub.png" alt="" aria-hidden="true" className="h-3.5 w-3.5 shrink-0 object-contain" />
      {`Сэкономьте ${percent}% с PS+`}
    </span>
  )
}
