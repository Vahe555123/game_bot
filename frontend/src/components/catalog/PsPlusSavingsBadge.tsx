import clsx from 'clsx'

type PsPlusSavingsBadgeProps = {
  percent?: number | null
  className?: string
}

export function PsPlusSavingsBadge({ percent, className }: PsPlusSavingsBadgeProps) {
  const hasSavingsPercent = typeof percent === 'number' && Number.isFinite(percent) && percent > 0

  return (
    <span
      className={clsx(
        'pill border-[#f4b526] bg-gradient-to-r from-[#ffd54a] to-[#f5a623] px-3 py-1.5 text-[13px] font-bold tracking-normal text-slate-950 shadow-lg shadow-amber-950/20',
        className,
      )}
    >
      <img src="/static/images/psplussub.png" alt="" aria-hidden="true" className="h-3.5 w-3.5 shrink-0 object-contain" />
      {hasSavingsPercent ? `Сэкономьте ${percent}% с PS+` : 'Сэкономьте с PS+'}
    </span>
  )
}
