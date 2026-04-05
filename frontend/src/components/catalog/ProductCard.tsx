import { BadgePercent, Gamepad2 } from 'lucide-react'
import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { useFavorites } from '../../context/FavoritesContext'
import type { CatalogProduct } from '../../types/catalog'
import { normalizeImageUrl, resolveRegionPresentation } from '../../utils/format'
import { getProductTitle, getVisibleRegionalPrices } from '../../utils/productPresentation'
import { FavoriteButton } from './FavoriteButton'
import { LocalizationBadge } from './LocalizationBadge'
import { RegionalPriceList } from './RegionalPriceList'

type ProductCardProps = {
  product: CatalogProduct
}

export function ProductCard({ product }: ProductCardProps) {
  const { isFavorite, toggleFavorite } = useFavorites()

  const imageUrl = normalizeImageUrl(product.image)
  const region = resolveRegionPresentation(product.routeRegion || product.region, product.regionInfo?.name)
  const productUrl = `/catalog/${product.id}${product.routeRegion ? `?region=${encodeURIComponent(product.routeRegion)}` : ''}`
  const regionalPrices = getVisibleRegionalPrices(product).slice(0, 3)
  const favoriteActive = isFavorite(product.id)
  const productTitle = getProductTitle(product)

  function handleFavoriteClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    toggleFavorite({
      productId: product.id,
      region: product.routeRegion || product.region,
    })
  }

  return (
    <article className="group relative h-full overflow-hidden rounded-[24px] border border-white/10 bg-slate-950/80 shadow-card transition duration-300 hover:-translate-y-1 hover:border-brand-300/40 hover:shadow-glow">
      <Link
        to={productUrl}
        aria-label={`Открыть ${productTitle}`}
        className="absolute inset-0 z-10 rounded-[24px]"
      />

      <div className="relative aspect-[16/10] overflow-hidden bg-gradient-to-br from-brand-500/25 via-slate-950 to-slate-900">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={productTitle}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
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

        <div className="absolute left-4 top-4 flex flex-wrap gap-2">
          <span className="pill bg-slate-950/70 text-brand-50">{region.label}</span>
          {product.hasDiscount ? (
            <span className="pill border-rose-400/20 bg-rose-500/20 text-rose-100">
              <BadgePercent size={12} />
              {product.discountPercent ? `-${product.discountPercent}%` : 'Скидка'}
            </span>
          ) : null}
          {product.hasPsPlus ? (
            <span className="pill border-amber-300/20 bg-amber-400/20 text-amber-50">PS Plus</span>
          ) : null}
        </div>

        <FavoriteButton
          active={favoriteActive}
          onClick={handleFavoriteClick}
          className="absolute right-4 top-4 z-20"
        />
      </div>

      <div className="relative z-0 space-y-4 p-4">
        <div className="space-y-3">
          <h3 className="line-clamp-2 min-h-[3.5rem] text-xl text-white">{productTitle}</h3>

          <div className="flex flex-wrap gap-2">
            {product.platforms ? (
              <span className="pill border-white/10 bg-white/5 text-slate-200">{product.platforms}</span>
            ) : null}
            <LocalizationBadge localizationName={product.localizationName} />
          </div>
        </div>

        <RegionalPriceList prices={regionalPrices} variant="card" />
      </div>
    </article>
  )
}
