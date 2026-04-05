import clsx from 'clsx'
import { Languages } from 'lucide-react'
import { getLocalizationPresentation } from '../../utils/productPresentation'

type LocalizationBadgeProps = {
  localizationName?: string | null
  className?: string
}

export function LocalizationBadge({ localizationName, className }: LocalizationBadgeProps) {
  const localization = getLocalizationPresentation(localizationName)

  return (
    <span
      title={localization.fullLabel}
      className={clsx(
        'pill',
        localization.status === 'supported' && 'border-emerald-400/20 bg-emerald-500/15 text-emerald-50',
        localization.status === 'unsupported' && 'border-rose-400/20 bg-rose-500/15 text-rose-50',
        localization.status === 'unknown' && 'border-white/10 bg-white/5 text-slate-200',
        className,
      )}
    >
      <Languages size={12} />
      {localization.shortLabel}
    </span>
  )
}
