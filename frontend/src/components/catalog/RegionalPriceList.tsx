import clsx from 'clsx'
import { BadgePercent } from 'lucide-react'
import type { ProductRegionPrice } from '../../types/catalog'
import { getDualCurrencyPriceDisplay } from '../../utils/format'
import { shouldShowOldPrice } from '../../utils/productPresentation'

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

  return (
    <div
      className={clsx(
        'rounded-2xl border border-white/10 bg-white/[0.04]',
        variant === 'card' ? 'px-3 py-2.5' : 'px-4 py-3.5',
      )}
    >
      <div className="flex items-center gap-3">
        <span
          className={clsx(
            'flex shrink-0 items-center justify-center rounded-full border border-white/10 bg-brand-500/15 font-black text-brand-50',
            variant === 'card' ? 'h-8 min-w-8 text-[11px]' : 'h-10 min-w-10 text-xs',
          )}
        >
          {price.label || price.region}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className={clsx('truncate font-semibold text-white', variant === 'card' ? 'text-sm' : 'text-base')}>
                {price.name}
              </p>
              {variant === 'detail' && price.localizationName ? (
                <p className="mt-1 truncate text-xs text-slate-400">{price.localizationName}</p>
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
            <span className={clsx('font-display text-white', variant === 'card' ? 'text-base' : 'text-2xl')}>
              {currentPrice.primary}
            </span>

            {currentPrice.secondary ? (
              <span className="text-xs font-medium text-slate-400">{currentPrice.secondary}</span>
            ) : null}

            {oldPrice ? (
              <span className="text-xs text-slate-500 line-through">{oldPrice.primary}</span>
            ) : null}

            {oldPrice?.secondary ? (
              <span className="text-xs text-slate-600 line-through">{oldPrice.secondary}</span>
            ) : null}

            {psPlusPrice ? (
              <span className="text-xs font-medium text-amber-200">
                PS Plus {psPlusPrice.primary}
                {psPlusPrice.secondary ? <span className="ml-1 text-amber-100/80">• {psPlusPrice.secondary}</span> : null}
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
      <div className={clsx('rounded-2xl border border-dashed border-white/10 bg-white/[0.03] px-4 py-5 text-sm text-slate-400', className)}>
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
