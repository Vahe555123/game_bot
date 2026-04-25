import { BadgePercent, Gamepad2 } from 'lucide-react'
import type { MouseEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useFavorites } from '../../context/FavoritesContext'
import type { CatalogProduct } from '../../types/catalog'
import { normalizeImageUrl } from '../../utils/format'
import {
  getProductLocalizationPresentation,
  getProductPsPlusSavingsPercent,
  getProductRegularDiscountPercent,
  getProductTitle,
  getProductVrLabel,
  getVisibleRegionalPrices,
} from '../../utils/productPresentation'
import { FavoriteButton } from './FavoriteButton'
import { LocalizationBadge } from './LocalizationBadge'
import { PsPlusSavingsBadge } from './PsPlusSavingsBadge'
import { RegionalPriceList } from './RegionalPriceList'

type ProductCardProps = {
  product: CatalogProduct
}

export function ProductCard({ product }: ProductCardProps) {
  const { isFavorite, toggleFavorite } = useFavorites()
  const location = useLocation()

  const imageUrl = normalizeImageUrl(product.image)
  const productUrl = `/catalog/${product.id}`
  const catalogPath =
    location.pathname === '/' || location.pathname === '/catalog'
      ? `${location.pathname}${location.search}${location.hash}`
      : null
  const regionalPrices = getVisibleRegionalPrices(product).slice(0, 3)
  const favoriteActive = isFavorite(product.id)
  const productTitle = getProductTitle(product)
  const psPlusSavingsPercent = getProductPsPlusSavingsPercent(product)
  const regularDiscountPercent = getProductRegularDiscountPercent(product)
  const localization = getProductLocalizationPresentation(product)
  const vrLabel = getProductVrLabel(product)
  const platformLabel = [product.platforms, vrLabel].filter(Boolean).join(' • ')

  function handleFavoriteClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    toggleFavorite({
      productId: product.id,
      region: product.region,
    })
  }

  return (
    <article className="group relative h-full overflow-hidden rounded-[20px] border border-white/10 bg-slate-950/80 shadow-card transition duration-300 hover:-translate-y-1 hover:border-brand-300/40 hover:shadow-glow md:rounded-[24px]">
      <Link
        to={productUrl}
        state={catalogPath ? { catalogPath } : undefined}
        aria-label={`Открыть ${productTitle}`}
        className="absolute inset-0 z-10 rounded-[20px] md:rounded-[24px]"
      />

      <div className="relative aspect-square overflow-hidden bg-gradient-to-br from-brand-500/20 via-slate-950 to-slate-900">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={productTitle}
            className="h-full w-full object-contain p-2.5 transition duration-500 group-hover:scale-[1.02] md:p-3"
            loading="lazy"
          />
        ) : (
          <div className="mesh-bg flex h-full w-full items-center justify-center px-6 text-center">
            <div>
              <Gamepad2 className="mx-auto h-10 w-10 text-brand-200/70" />
              <p className="mt-3 text-sm font-semibold text-white/90">{productTitle}</p>
            </div>
          </div>
        )}

        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />

        <div className="absolute left-2.5 right-14 top-2.5 flex flex-wrap gap-1.5 md:left-4 md:right-16 md:top-4 md:gap-2">
          {regularDiscountPercent ? (
            <span className="pill border-rose-400/40 bg-rose-500 px-2.5 py-1 text-[11px] text-white shadow-lg shadow-rose-950/30">
              <BadgePercent size={12} />
              -{regularDiscountPercent}%
            </span>
          ) : null}
          {psPlusSavingsPercent ? (
            <PsPlusSavingsBadge percent={psPlusSavingsPercent} className="px-2.5 py-1 text-[13px]" />
          ) : null}
          {product.hasEaAccess ? (
            <span className="pill border-[#3b82f6] bg-[#2563eb] px-2.5 py-1 text-[11px] text-white shadow-lg shadow-blue-950/30">
              EA PLAY
            </span>
          ) : null}
        </div>

        <FavoriteButton active={favoriteActive} onClick={handleFavoriteClick} className="absolute right-2.5 top-2.5 z-20 md:right-4 md:top-4" />

        <div className="absolute inset-x-2.5 bottom-2.5 flex flex-wrap gap-1.5 md:inset-x-3 md:bottom-3 md:gap-2">
          {platformLabel ? (
            <span className="pill border-white/10 bg-slate-950/85 px-2.5 py-1 text-[11px] text-slate-100 shadow-lg">
              {platformLabel}
            </span>
          ) : null}
          <LocalizationBadge
            localizationName={localization.fullLabel}
            className="px-2.5 py-1 text-[11px] shadow-lg backdrop-blur-sm md:text-xs"
          />
        </div>
      </div>

      <div className="relative z-0 space-y-3 p-3 md:space-y-4 md:p-4">
        <div className="space-y-1.5 md:space-y-2">
          <h3 className="line-clamp-3 min-h-[3.65rem] text-[15px] leading-[1.22] text-white md:min-h-[4.35rem] md:text-lg md:leading-[1.2]">
            {productTitle}
          </h3>
        </div>

        <RegionalPriceList prices={regionalPrices} variant="card" />
      </div>
    </article>
  )
}
