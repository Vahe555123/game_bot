import clsx from 'clsx'
import type { ReactNode } from 'react'

type SectionHeaderProps = {
  eyebrow: string
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div className={clsx('flex flex-col gap-4 md:flex-row md:items-end md:justify-between', className)}>
      <div className="max-w-2xl">
        <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">{eyebrow}</p>
        <h2 className="mt-3 font-display text-3xl text-white md:text-4xl">{title}</h2>
        {description ? <p className="mt-3 text-base text-slate-300">{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  )
}
