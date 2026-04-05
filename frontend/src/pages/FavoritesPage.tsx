import { Heart, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ProductCard } from '../components/catalog/ProductCard'
import { ProductSkeleton } from '../components/catalog/ProductSkeleton'
import { SectionHeader } from '../components/common/SectionHeader'
import { useFavorites } from '../context/FavoritesContext'
import { mockProducts } from '../data/mockProducts'
import { fetchProduct } from '../services/catalog'
import type { CatalogProduct } from '../types/catalog'

function sortFavoritesByDate(products: CatalogProduct[], orderedIds: string[]) {
  const orderMap = new Map(orderedIds.map((productId, index) => [productId, index]))

  return [...products].sort((left, right) => {
    const leftOrder = orderMap.get(left.id) ?? Number.MAX_SAFE_INTEGER
    const rightOrder = orderMap.get(right.id) ?? Number.MAX_SAFE_INTEGER
    return leftOrder - rightOrder
  })
}

export function FavoritesPage() {
  const { favorites } = useFavorites()
  const [products, setProducts] = useState<CatalogProduct[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const orderedFavorites = useMemo(
    () =>
      [...favorites].sort(
        (left, right) => new Date(right.addedAt).getTime() - new Date(left.addedAt).getTime(),
      ),
    [favorites],
  )

  useEffect(() => {
    let ignore = false

    if (!orderedFavorites.length) {
      setProducts([])
      setIsLoading(false)
      return
    }

    setIsLoading(true)

    ;(async () => {
      const loadedProducts = await Promise.allSettled(
        orderedFavorites.map(async (entry) => {
          try {
            return await fetchProduct(entry.productId, entry.region || undefined)
          } catch {
            return mockProducts.find((product) => product.id === entry.productId) ?? null
          }
        }),
      )

      if (ignore) {
        return
      }

      const resolvedProducts = loadedProducts
        .map((result) => (result.status === 'fulfilled' ? result.value : null))
        .filter((product): product is CatalogProduct => Boolean(product))
      setProducts(sortFavoritesByDate(resolvedProducts, orderedFavorites.map((entry) => entry.productId)))
      setIsLoading(false)
    })()

    return () => {
      ignore = true
    }
  }, [orderedFavorites])

  return (
    <div className="container py-10 md:py-14">
      <SectionHeader
        eyebrow="Избранное"
        title="Твои сохранённые игры"
        description="Список повторяет логику miniapp: сюда попадают товары, которые ты отметил сердцем в каталоге или на внутренней странице."
        action={
          <Link to="/catalog" className="btn-secondary">
            <Search size={16} />
            В каталог
          </Link>
        }
      />

      <div className="mt-8">
        {!orderedFavorites.length ? (
          <div className="panel-soft rounded-[32px] px-6 py-14 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-rose-500/15 text-rose-200">
              <Heart className="h-8 w-8" />
            </div>
            <h2 className="mt-6 text-2xl text-white">Пока ничего не добавлено</h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              Нажми на сердце в карточке или на странице товара, и игра сразу появится здесь.
            </p>
            <Link to="/catalog" className="btn-primary mt-6">
              Перейти в каталог
            </Link>
          </div>
        ) : (
          <>
            <div className="panel-soft rounded-[28px] p-4 md:p-5">
              <div className="flex flex-col gap-2 text-sm text-slate-400 md:flex-row md:items-center md:justify-between">
                <p>
                  В избранном <span className="font-semibold text-white">{orderedFavorites.length}</span> товаров
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {isLoading
                ? Array.from({ length: Math.min(orderedFavorites.length, 6) }).map((_, index) => (
                    <ProductSkeleton key={index} />
                  ))
                : products.map((product) => <ProductCard key={`${product.id}-${product.routeRegion || 'all'}`} product={product} />)}
            </div>

            {!isLoading && !products.length ? (
              <div className="panel-soft mt-6 rounded-[28px] px-6 py-12 text-center text-slate-300">
                Не удалось загрузить  сохранённые товары. Попробуй открыть каталог и добавить их заново.
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
