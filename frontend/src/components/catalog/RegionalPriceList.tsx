import clsx from 'clsx'
import { BadgePercent } from 'lucide-react'
import type { ProductRegionPrice } from '../../types/catalog'
import { getDualCurrencyPriceDisplay } from '../../utils/format'
import { getEffectiveRegionalPrice, getLocalizationPresentation, shouldShowOldPrice } from '../../utils/productPresentation'

type RegionalPriceListProps = {
  prices: ProductRegionPrice[]
  variant?: 'card' | 'detail'
  className?: string
}

function UnavailableRegionRow({
  price,
  variant,
}: {
  price: ProductRegionPrice
  variant: 'card' | 'detail'
}) {
  return (
    <div
      className={clsx(
        'rounded-2xl border border-white/5 bg-white/[0.02]',
        variant === 'card' ? 'px-2.5 py-2 md:px-3 md:py-2.5' : 'px-4 py-3.5',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <p className={clsx('truncate font-semibold text-slate-500', variant === 'card' ? 'text-sm' : 'text-base')}>
          {price.name}
        </p>
        <span className="shrink-0 text-xs text-slate-600">Недоступно</span>
      </div>
    </div>
  )
}

function RegionalPriceRow({
  price,
  variant,
}: {
  price: ProductRegionPrice
  variant: 'card' | 'detail'
}) {
  if (!price.available) {
    return <UnavailableRegionRow price={price} variant={variant} />
  }

  const effectivePrice = getEffectiveRegionalPrice(price)
  const showOldPrice = shouldShowOldPrice(price)
  const currentPrice = getDualCurrencyPriceDisplay(
    effectivePrice.currentLocal,
    price.currencyCode,
    effectivePrice.currentRub,
  )
  const oldPrice = showOldPrice
    ? getDualCurrencyPriceDisplay(effectivePrice.oldLocal, price.currencyCode, effectivePrice.oldRub)
    : null
  const localization = getLocalizationPresentation(price.localizationName)

  return (
    <div
      className={clsx(
        'rounded-2xl border border-white/10 bg-white/[0.04]',
        variant === 'card' ? 'px-2.5 py-2 md:px-3 md:py-2.5' : 'px-4 py-3.5',
      )}
    >
      <div className="flex items-center gap-2.5 md:gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className={clsx('truncate font-semibold text-white', variant === 'card' ? 'text-sm' : 'text-base')}>
                {price.name}
              </p>
              {variant === 'detail' ? (
                <p
                  className={clsx(
                    'mt-1 truncate text-xs',
                    localization.status === 'full' && 'text-emerald-300',
                    localization.status === 'partial' && 'text-sky-300',
                    localization.status === 'unsupported' && 'text-rose-300',
                    localization.status === 'unknown' && 'text-slate-400',
                  )}
                >
                  {localization.shortLabel}
                </p>
              ) : null}
            </div>

            {price.hasDiscount && price.discountPercent ? (
              <span className="pill border-rose-400/20 bg-rose-500/15 px-2.5 py-1 text-[11px] text-rose-50">
                <BadgePercent size={11} />
                -{price.discountPercent}%
              </span>
            ) : null}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            {effectivePrice.isPsPlus ? (
              <span className="rounded-full border border-amber-300/35 bg-amber-400/15 px-2.5 py-1 text-[11px] font-semibold text-amber-100">
                PS Plus
              </span>
            ) : null}

            <span className={clsx('font-display text-white', variant === 'card' ? 'text-sm md:text-base' : 'text-2xl')}>
              {currentPrice.primary}
            </span>

            {currentPrice.secondary ? (
              <span className="text-[11px] font-medium text-slate-400 md:text-xs">{currentPrice.secondary}</span>
            ) : null}

            {oldPrice ? <span className="text-[11px] text-slate-500 line-through md:text-xs">{oldPrice.primary}</span> : null}

            {oldPrice?.secondary ? (
              <span className="text-[11px] text-slate-600 line-through md:text-xs">{oldPrice.secondary}</span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

export function RegionalPriceList({
  prices,
  variant = 'card',
  className,
}: RegionalPriceListProps) {
  if (!prices.length) {
    return (
      <div
        className={clsx(
          'rounded-2xl border border-dashed border-white/10 bg-white/[0.03] px-4 py-5 text-sm text-slate-400',
          className,
        )}
      >
        Цены обновляются. Попробуй открыть товар чуть позже.
      </div>
    )
  }

  return (
    <div className={clsx('space-y-2', className)}>
      {prices.map((price) => (
        <RegionalPriceRow key={`${price.region}-${price.name}`} price={price} variant={variant} />
      ))}
    </div>
  )
}
