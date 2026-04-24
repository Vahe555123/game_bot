import { Heart, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ProductCard } from '../components/catalog/ProductCard'
import { ProductSkeleton } from '../components/catalog/ProductSkeleton'
import { SectionHeader } from '../components/common/SectionHeader'
import { useFavorites } from '../context/FavoritesContext'
import { fetchProductsBatch } from '../services/catalog'
import type { CatalogProduct } from '../types/catalog'

const FAVORITES_PAGE_SIZE = 20

function buildFavoritesKey(products: { productId: string; region?: string | null; addedAt: string }[]) {
  return products.map((entry) => `${entry.productId}:${entry.region || 'all'}:${entry.addedAt}`).join('|')
}

function mergeFavoriteProducts(current: CatalogProduct[], next: CatalogProduct[]) {
  if (!current.length) {
    return next
  }

  const knownIds = new Set(current.map((product) => `${product.id}-${product.region || 'all'}`))
  const merged = [...current]

  next.forEach((product) => {
    const productKey = `${product.id}-${product.region || 'all'}`

    if (!knownIds.has(productKey)) {
      merged.push(product)
      knownIds.add(productKey)
    }
  })

  return merged
}

function dedupeFavoriteProducts(products: CatalogProduct[]) {
  const knownIds = new Set<string>()
  const result: CatalogProduct[] = []

  products.forEach((product) => {
    const productKey = `${product.id}-${product.region || 'all'}`

    if (!knownIds.has(productKey)) {
      knownIds.add(productKey)
      result.push(product)
    }
  })

  return result
}

export function FavoritesPage() {
  const { favorites, isFavoritesLoading } = useFavorites()
  const [products, setProducts] = useState<CatalogProduct[]>([])
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [favoritesNotice, setFavoritesNotice] = useState<string | null>(null)
  const previousFavoritesKeyRef = useRef<string>('')
  const loadMoreRef = useRef<HTMLDivElement | null>(null)

  const orderedFavorites = useMemo(
    () =>
      [...favorites].sort(
        (left, right) => new Date(right.addedAt).getTime() - new Date(left.addedAt).getTime(),
      ),
    [favorites],
  )
  const favoritesKey = useMemo(() => buildFavoritesKey(orderedFavorites), [orderedFavorites])
  const loadedCount = Math.min(products.length, orderedFavorites.length)
  const progressPercent = orderedFavorites.length ? Math.round((loadedCount / orderedFavorites.length) * 100) : 0

  useEffect(() => {
    const node = loadMoreRef.current

    if (!node) {
      return undefined
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (!entry?.isIntersecting || isLoading || isLoadingMore || !hasNextPage) {
          return
        }

        setPage((current) => current + 1)
      },
      {
        rootMargin: '320px 0px',
      },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [hasNextPage, isLoading, isLoadingMore])

  useEffect(() => {
    const favoritesChanged = previousFavoritesKeyRef.current !== favoritesKey

    if (favoritesChanged) {
      previousFavoritesKeyRef.current = favoritesKey
      setProducts([])
      setHasNextPage(false)
      setFavoritesNotice(null)

      if (page !== 1) {
        setPage(1)
        return
      }
    }

    if (!orderedFavorites.length) {
      setProducts([])
      setHasNextPage(false)
      setIsLoading(false)
      setIsLoadingMore(false)
      return
    }

    const sliceStart = (page - 1) * FAVORITES_PAGE_SIZE
    const pageEntries = orderedFavorites.slice(sliceStart, sliceStart + FAVORITES_PAGE_SIZE)

    if (!pageEntries.length) {
      setHasNextPage(false)
      setIsLoading(false)
      setIsLoadingMore(false)
      return
    }

    let ignore = false
    const isFirstPage = page === 1

    if (isFirstPage) {
      setIsLoading(true)
    } else {
      setIsLoadingMore(true)
    }

    ;(async () => {
      try {
        const response = await fetchProductsBatch(pageEntries.map((entry) => entry.productId))

        if (ignore) {
          return
        }

        const nextProducts = dedupeFavoriteProducts(response.products)
        setProducts((current) => (isFirstPage ? nextProducts : mergeFavoriteProducts(current, nextProducts)))
        setHasNextPage(sliceStart + pageEntries.length < orderedFavorites.length)
        setFavoritesNotice(null)
      } catch {
        if (ignore) {
          return
        }

        if (isFirstPage) {
          setProducts([])
        }

        setHasNextPage(false)
        setFavoritesNotice('Не удалось загрузить избранное. Попробуй обновить страницу чуть позже.')
      } finally {
        if (!ignore) {
          setIsLoading(false)
          setIsLoadingMore(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [favoritesKey, orderedFavorites, page])

  return (
    <div className="container py-10 md:py-14">
      <SectionHeader
        eyebrow="Избранное"
        title="Твои сохранённые игры"
        action={
          <Link to="/catalog" className="btn-secondary">
            <Search size={16} />
            В каталог
          </Link>
        }
      />

      <div className="mt-8">
        {isFavoritesLoading && !orderedFavorites.length ? (
          <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:gap-4 xl:grid-cols-4 2xl:grid-cols-5">
            {Array.from({ length: 6 }).map((_, index) => (
              <ProductSkeleton key={index} />
            ))}
          </div>
        ) : !orderedFavorites.length ? (
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
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1 text-sm text-slate-400">
                  <p>
                    В избранном <span className="font-semibold text-white">{orderedFavorites.length}</span> товаров
                  </p>
                  <p className="text-xs text-slate-500">
                    Загружено <span className="font-semibold text-slate-200">{loadedCount}</span> из{' '}
                    <span className="font-semibold text-slate-200">{orderedFavorites.length}</span>
                  </p>
                </div>

                <div className="w-full max-w-full md:max-w-xs">
                  <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
                    <span>Прогресс загрузки</span>
                    <span className="font-semibold text-slate-200">{progressPercent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-brand-300 via-sky-400 to-cyan-300 transition-[width] duration-300"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {favoritesNotice ? (
              <div className="mt-4 rounded-[22px] border border-amber-300/20 bg-amber-500/10 px-4 py-3 text-sm leading-7 text-amber-50">
                {favoritesNotice}
              </div>
            ) : null}

            <div className="mt-6 grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:gap-4 xl:grid-cols-4 2xl:grid-cols-5">
              {isLoading
                ? Array.from({ length: Math.min(Math.max(orderedFavorites.length, 6), FAVORITES_PAGE_SIZE) }).map((_, index) => (
                    <ProductSkeleton key={index} />
                  ))
                : products.map((product) => <ProductCard key={`${product.id}-${product.region || 'all'}`} product={product} />)}
            </div>

            {!isLoading && !products.length ? (
              <div className="panel-soft mt-6 rounded-[28px] px-6 py-12 text-center text-slate-300">
                Не удалось собрать карточки избранного. Попробуй обновить страницу или открыть каталог заново.
              </div>
            ) : null}

            {products.length > 0 ? (
              <div ref={loadMoreRef} className="mt-8 flex min-h-16 items-center justify-center">
                {isLoadingMore ? (
                  <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
                    Загружаем следующие 20 игр...
                  </div>
                ) : hasNextPage ? (
                  <div className="text-sm text-slate-500">Прокрути ниже, чтобы автоматически загрузить ещё 20 игр</div>
                ) : (
                  <div className="text-sm text-slate-500">Все избранные игры уже загружены</div>
                )}
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
