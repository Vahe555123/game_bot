import { Search, SlidersHorizontal } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CatalogFilters } from '../components/catalog/CatalogFilters'
import { ProductCard } from '../components/catalog/ProductCard'
import { ProductSkeleton } from '../components/catalog/ProductSkeleton'
import { mockProducts } from '../data/mockProducts'
import { fetchCatalog, fetchCategories } from '../services/catalog'
import type { CatalogFilterState, CatalogProduct } from '../types/catalog'
import {
  matchesPlatformFilter,
  matchesPlayersFilter,
  matchesPriceRange,
  normalizeRegionFilterValue,
  sanitizeCatalogFilters,
} from '../utils/catalogFilters'

const DEFAULT_FILTERS: CatalogFilterState = {
  page: 1,
  limit: 16,
  sort: 'popular',
  search: '',
  category: '',
  region: '',
  platform: '',
  players: '',
  minPrice: '',
  maxPrice: '',
  hasDiscount: false,
  hasPsPlus: false,
  hasEaAccess: false,
}

function parseFilters(searchParams: URLSearchParams): CatalogFilterState {
  const pageValue = Number(searchParams.get('page') || '1')

  return sanitizeCatalogFilters({
    ...DEFAULT_FILTERS,
    page: Number.isFinite(pageValue) && pageValue > 0 ? pageValue : 1,
    sort: searchParams.get('sort') || 'popular',
    search: searchParams.get('search') || '',
    category: searchParams.get('category') || '',
    region: searchParams.get('region') || '',
    platform: searchParams.get('platform') || '',
    players: searchParams.get('players') || '',
    minPrice: searchParams.get('minPrice') || '',
    maxPrice: searchParams.get('maxPrice') || '',
    hasDiscount: searchParams.get('hasDiscount') === 'true',
    hasPsPlus: searchParams.get('hasPsPlus') === 'true',
    hasEaAccess: searchParams.get('hasEaAccess') === 'true',
  })
}

function buildSearchParams(filters: CatalogFilterState) {
  const next = new URLSearchParams()

  if (filters.sort && filters.sort !== 'popular') next.set('sort', filters.sort)
  if (filters.search) next.set('search', filters.search)
  if (filters.category) next.set('category', filters.category)
  if (filters.region) next.set('region', filters.region)
  if (filters.platform) next.set('platform', filters.platform)
  if (filters.players) next.set('players', filters.players)
  if (filters.minPrice) next.set('minPrice', filters.minPrice)
  if (filters.maxPrice) next.set('maxPrice', filters.maxPrice)
  if (filters.hasDiscount) next.set('hasDiscount', 'true')
  if (filters.hasPsPlus) next.set('hasPsPlus', 'true')
  if (filters.hasEaAccess) next.set('hasEaAccess', 'true')

  return next
}

function areFiltersEqual(left: CatalogFilterState, right: CatalogFilterState) {
  return (
    left.page === right.page &&
    left.limit === right.limit &&
    left.sort === right.sort &&
    left.search === right.search &&
    left.category === right.category &&
    left.region === right.region &&
    left.platform === right.platform &&
    left.players === right.players &&
    left.minPrice === right.minPrice &&
    left.maxPrice === right.maxPrice &&
    left.hasDiscount === right.hasDiscount &&
    left.hasPsPlus === right.hasPsPlus &&
    left.hasEaAccess === right.hasEaAccess
  )
}

function countActiveFilters(filters: CatalogFilterState) {
  return [
    filters.category,
    filters.region,
    filters.platform,
    filters.players,
    filters.minPrice || filters.maxPrice,
    filters.hasDiscount,
    filters.hasPsPlus,
    filters.hasEaAccess,
  ].filter(Boolean).length
}

function applyMockFilters(products: CatalogProduct[], filters: CatalogFilterState) {
  const normalizedRegion = normalizeRegionFilterValue(filters.region)

  const filtered = products
    .filter((product) => {
      const matchesSearch =
        !filters.search ||
        [product.mainName, product.name, product.publisher, product.category, ...product.tags]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
          .includes(filters.search.toLowerCase())

      const matchesCategory = !filters.category || product.category === filters.category
      const matchesRegion = !normalizedRegion || product.region === normalizedRegion
      const matchesPlatform = matchesPlatformFilter(product, filters.platform)
      const matchesPlayers = matchesPlayersFilter(product, filters.players)
      const matchesPrice = matchesPriceRange(product, filters.minPrice, filters.maxPrice)
      const matchesDiscount = !filters.hasDiscount || product.hasDiscount
      const matchesPsPlus = !filters.hasPsPlus || product.hasPsPlus
      const matchesEaAccess = !filters.hasEaAccess || product.hasEaAccess

      return (
        matchesSearch &&
        matchesCategory &&
        matchesRegion &&
        matchesPlatform &&
        matchesPlayers &&
        matchesPrice &&
        matchesDiscount &&
        matchesPsPlus &&
        matchesEaAccess
      )
    })
    .sort((left, right) => {
      if (filters.sort === 'alphabet') {
        return left.mainName.localeCompare(right.mainName, 'ru')
      }

      if (filters.sort === 'price_asc') {
        const leftPrice = left.priceRub ?? Number.POSITIVE_INFINITY
        const rightPrice = right.priceRub ?? Number.POSITIVE_INFINITY
        return leftPrice - rightPrice || left.mainName.localeCompare(right.mainName, 'ru')
      }

      return (right.favoritesCount ?? 0) - (left.favoritesCount ?? 0) || left.mainName.localeCompare(right.mainName, 'ru')
    })

  const start = (filters.page - 1) * filters.limit
  const end = start + filters.limit

  return {
    products: filtered.slice(start, end),
    total: filtered.length,
    hasNext: end < filtered.length,
  }
}

function mergeCatalogProducts(current: CatalogProduct[], next: CatalogProduct[]) {
  if (!current.length) {
    return next
  }

  const knownIds = new Set(current.map((product) => `${product.id}-${product.routeRegion || product.region || 'all'}`))
  const merged = [...current]

  next.forEach((product) => {
    const productKey = `${product.id}-${product.routeRegion || product.region || 'all'}`

    if (!knownIds.has(productKey)) {
      merged.push(product)
      knownIds.add(productKey)
    }
  })

  return merged
}

function dedupeCatalogProducts(products: CatalogProduct[]) {
  const knownIds = new Set<string>()
  const result: CatalogProduct[] = []

  products.forEach((product) => {
    const productKey = `${product.id}-${product.routeRegion || product.region || 'all'}`

    if (!knownIds.has(productKey)) {
      knownIds.add(productKey)
      result.push(product)
    }
  })

  return result
}

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(searchParams), [searchParams])
  const filtersKey = useMemo(() => buildSearchParams({ ...filters, page: 1 }).toString(), [filters])

  const [draftSearch, setDraftSearch] = useState(filters.search)
  const [draftFilters, setDraftFilters] = useState(filters)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [isMobileFiltersOpen, setIsMobileFiltersOpen] = useState(false)
  const [products, setProducts] = useState<CatalogProduct[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [catalogNotice, setCatalogNotice] = useState<string | null>(null)
  const previousFiltersKeyRef = useRef(filtersKey)
  const loadMoreRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setDraftSearch(filters.search)
    setDraftFilters(filters)
  }, [filters])

  useEffect(() => {
    let ignore = false

    ;(async () => {
      try {
        const apiCategories = await fetchCategories()
        if (!ignore) {
          setCategories(apiCategories.length ? apiCategories : ['Экшен', 'RPG', 'Новинки', 'Спорт'])
        }
      } catch {
        if (!ignore) {
          setCategories(['Экшен', 'RPG', 'Новинки', 'Спорт', 'Приключения'])
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    const normalizedFilters = sanitizeCatalogFilters(filters, categories)

    if (!areFiltersEqual(filters, normalizedFilters)) {
      setSearchParams(buildSearchParams(normalizedFilters), { replace: true })
    }
  }, [categories, filters, setSearchParams])

  useEffect(() => {
    const nextFilters = {
      ...draftFilters,
      search: draftSearch.trim(),
      page: 1,
      limit: DEFAULT_FILTERS.limit,
    }
    const currentFilters = {
      ...filters,
      page: 1,
      limit: DEFAULT_FILTERS.limit,
    }

    const nextParams = buildSearchParams(nextFilters).toString()
    const currentParams = buildSearchParams(currentFilters).toString()

    if (nextParams === currentParams) {
      return undefined
    }

    const timeoutId = window.setTimeout(() => {
      setSearchParams(buildSearchParams(nextFilters), { replace: true })
      setIsMobileFiltersOpen(false)
    }, 1000)

    return () => window.clearTimeout(timeoutId)
  }, [draftFilters, draftSearch, filters, setSearchParams])

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
    const filtersChanged = previousFiltersKeyRef.current !== filtersKey

    if (filtersChanged) {
      previousFiltersKeyRef.current = filtersKey
      setProducts([])
      setTotal(0)
      setHasNextPage(false)

      if (page !== 1) {
        setPage(1)
        return
      }
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
        let response = await fetchCatalog({
          page,
          limit: filters.limit,
          sort: filters.sort,
          search: filters.search || undefined,
          category: filters.category || undefined,
          region: filters.region || undefined,
          platform: filters.platform || undefined,
          players: filters.players || undefined,
          min_price: filters.minPrice ? Number(filters.minPrice) : undefined,
          max_price: filters.maxPrice ? Number(filters.maxPrice) : undefined,
          has_discount: filters.hasDiscount || undefined,
          has_ps_plus: filters.hasPsPlus || undefined,
          has_ea_access: filters.hasEaAccess || undefined,
          grouped: true,
        })

        let notice: string | null = null

        if (isFirstPage && response.total === 0 && response.products.length === 0) {
          const fallbackResponse = await fetchCatalog({
            page,
            limit: Math.max(filters.limit * 3, 24),
            sort: filters.sort,
            search: filters.search || undefined,
            category: filters.category || undefined,
            region: filters.region || undefined,
            platform: filters.platform || undefined,
            players: filters.players || undefined,
            min_price: filters.minPrice ? Number(filters.minPrice) : undefined,
            max_price: filters.maxPrice ? Number(filters.maxPrice) : undefined,
            has_discount: filters.hasDiscount || undefined,
            has_ps_plus: filters.hasPsPlus || undefined,
            has_ea_access: filters.hasEaAccess || undefined,
            grouped: false,
          })

          if (fallbackResponse.products.length > 0) {
            response = {
              ...fallbackResponse,
              products: dedupeCatalogProducts(fallbackResponse.products).slice(0, filters.limit),
              total: fallbackResponse.total,
              hasNext: fallbackResponse.hasNext,
            }
            notice = 'Каталог восстановлен через резервную загрузку. Если увидите странные дубли, обновите страницу.'
          }
        }

        if (!ignore) {
          setProducts((current) =>
            isFirstPage
              ? dedupeCatalogProducts(response.products)
              : mergeCatalogProducts(current, dedupeCatalogProducts(response.products)),
          )
          setTotal(response.total)
          setHasNextPage(response.hasNext)
          setCatalogNotice(notice)
        }
      } catch {
        if (!ignore) {
          const fallback = applyMockFilters(mockProducts, { ...filters, page })
          setProducts((current) =>
            isFirstPage
              ? dedupeCatalogProducts(fallback.products)
              : mergeCatalogProducts(current, dedupeCatalogProducts(fallback.products)),
          )
          setTotal(fallback.total)
          setHasNextPage(fallback.hasNext)
          setCatalogNotice('Не удалось получить живой каталог. Показываю резервную подборку, пока API не ответит.')
        }
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
  }, [filters, filtersKey, page])

  const activeFiltersCount = countActiveFilters(filters)

  function updateDraftFilters(partial: Partial<CatalogFilterState>) {
    setDraftFilters((current) => ({
      ...current,
      ...partial,
    }))
  }

  function resetDraftFilters() {
    const nextFilters = {
      ...DEFAULT_FILTERS,
      page: 1,
      limit: filters.limit,
    }

    setDraftSearch('')
    setDraftFilters(nextFilters)
    setSearchParams(buildSearchParams(nextFilters), { replace: true })
    setIsMobileFiltersOpen(false)
  }

  return (
    <div className="container py-4 md:py-6">
      <section className="sticky top-[5.25rem] z-30 rounded-[24px] border border-white/10 bg-slate-950/92 p-3 shadow-card backdrop-blur-xl md:top-24 md:rounded-[30px] md:p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <label className="input-shell flex-1">
            <Search size={18} className="text-brand-300" />
            <input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Поиск игр и подписок..."
              className="w-full bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
            />
          </label>

          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto md:gap-3">
            <div className="w-full rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 sm:w-auto md:px-4 md:text-sm">
              <span className="font-semibold text-white">{total}</span> товаров
              {activeFiltersCount > 0 ? `, фильтров: ${activeFiltersCount}` : ''}
            </div>

            <button
              type="button"
              onClick={() => setIsMobileFiltersOpen((value) => !value)}
              className="btn-secondary xl:hidden"
            >
              <SlidersHorizontal size={16} />
              Фильтры
            </button>
          </div>
        </div>

        <CatalogFilters
          categories={categories}
          draftFilters={draftFilters}
          onDraftChange={updateDraftFilters}
          onReset={resetDraftFilters}
          className={isMobileFiltersOpen ? 'mt-4 block' : 'mt-4 hidden xl:block'}
        />

      </section>

      {catalogNotice ? (
        <div className="mt-4 rounded-[22px] border border-amber-300/20 bg-amber-500/10 px-4 py-3 text-sm leading-7 text-amber-50">
          {catalogNotice}
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:mt-6 md:gap-4 lg:grid-cols-3 2xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: filters.limit }).map((_, index) => <ProductSkeleton key={index} />)
          : products.map((product) => <ProductCard key={`${product.id}-${product.routeRegion || product.region || 'all'}`} product={product} />)}
      </div>

      {!isLoading && products.length === 0 ? (
        <div className="panel-soft mt-6 rounded-[24px] px-5 py-10 text-center text-slate-300 md:rounded-[28px] md:px-6 md:py-12">
          <p>По этим параметрам товаров пока не нашлось.</p>
          <p className="mt-2 text-sm text-slate-400">Попробуй изменить поиск или очистить фильтры.</p>
          <div className="mt-5 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button type="button" onClick={resetDraftFilters} className="btn-primary">
              Сбросить фильтры
            </button>
            <Link to="/catalog" className="btn-secondary">
              Открыть каталог заново
            </Link>
          </div>
        </div>
      ) : null}

      {products.length > 0 ? (
        <div ref={loadMoreRef} className="mt-8 flex min-h-16 items-center justify-center">
          {isLoadingMore ? (
            <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
              Загружаем еще...
            </div>
          ) : hasNextPage ? (
            <div className="text-sm text-slate-500">Прокрути ниже, чтобы загрузить следующие товары</div>
          ) : (
            <div className="text-sm text-slate-500">Каталог загружен полностью</div>
          )}
        </div>
      ) : null}
    </div>
  )
}
