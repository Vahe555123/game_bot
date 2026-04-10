import clsx from 'clsx'
import { BadgePercent } from 'lucide-react'
import type { ProductRegionPrice } from '../../types/catalog'
import { getDualCurrencyPriceDisplay } from '../../utils/format'
import { getLocalizationPresentation, shouldShowOldPrice } from '../../utils/productPresentation'

type RegionalPriceListProps = {
  prices: ProductRegionPrice[]
  variant?: 'card' | 'detail'
  className?: string
}

function RegionalPriceRow({
  price,
  variant,
}: {
  price: ProductRegionPrice
  variant: 'card' | 'detail'
}) {
  const showOldPrice = shouldShowOldPrice(price)
  const currentPrice = getDualCurrencyPriceDisplay(price.priceLocal, price.currencyCode, price.priceRub)
  const oldPrice = showOldPrice
    ? getDualCurrencyPriceDisplay(price.oldPriceLocal, price.currencyCode, price.oldPriceRub)
    : null
  const psPlusPrice =
    variant === 'detail' && price.psPlusPriceRub !== null
      ? getDualCurrencyPriceDisplay(price.psPlusPriceLocal, price.currencyCode, price.psPlusPriceRub)
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

            {psPlusPrice ? (
              <span className="text-xs font-medium text-amber-200">
                PS Plus {psPlusPrice.primary}
                {psPlusPrice.secondary ? <span className="ml-1 text-amber-100/80">/ {psPlusPrice.secondary}</span> : null}
              </span>
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
