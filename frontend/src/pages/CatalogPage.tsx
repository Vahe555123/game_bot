import { Search, SlidersHorizontal } from 'lucide-react'
import clsx from 'clsx'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CatalogFilters } from '../components/catalog/CatalogFilters'
import { ProductCard } from '../components/catalog/ProductCard'
import { ProductSkeleton } from '../components/catalog/ProductSkeleton'
import { useAuth } from '../context/AuthContext'
import { fetchCatalog, fetchCategories } from '../services/catalog'
import type { CatalogFilterState, CatalogProduct } from '../types/catalog'
import { sanitizeCatalogFilters } from '../utils/catalogFilters'

const DEFAULT_FILTERS: CatalogFilterState = {
  page: 1,
  limit: 16,
  sort: 'popular',
  search: '',
  category: '',
  productKind: 'all',
  region: '',
  priceCurrency: 'RUB',
  platform: '',
  players: '',
  gameLanguage: '',
  minPrice: '',
  maxPrice: '',
  hasDiscount: false,
  hasPsPlus: false,
  hasEaAccess: false,
}

const CATALOG_PRODUCT_KIND_STORAGE_PREFIX = 'catalog_product_kind'

function getProductKindStorageKey(userId?: string | null) {
  return `${CATALOG_PRODUCT_KIND_STORAGE_PREFIX}:${userId || 'guest'}`
}

function readStoredProductKind(storageKey: string) {
  if (typeof window === 'undefined') {
    return DEFAULT_FILTERS.productKind
  }

  return window.localStorage.getItem(storageKey) || DEFAULT_FILTERS.productKind
}

function parseFilters(searchParams: URLSearchParams, storedProductKind = DEFAULT_FILTERS.productKind): CatalogFilterState {
  const pageValue = Number(searchParams.get('page') || '1')

  return sanitizeCatalogFilters({
    ...DEFAULT_FILTERS,
    page: Number.isFinite(pageValue) && pageValue > 0 ? pageValue : 1,
    sort: searchParams.get('sort') || 'popular',
    search: searchParams.get('search') || '',
    category: searchParams.get('category') || '',
    productKind: searchParams.get('productKind') || storedProductKind,
    region: '',
    priceCurrency: searchParams.get('priceCurrency') || 'RUB',
    platform: searchParams.get('platform') || '',
    players: searchParams.get('players') || '',
    gameLanguage: searchParams.get('gameLanguage') || '',
    minPrice: searchParams.get('minPrice') || '',
    maxPrice: searchParams.get('maxPrice') || '',
    hasDiscount: searchParams.get('hasDiscount') === 'true',
    hasPsPlus: searchParams.get('hasPsPlus') === 'true',
    hasEaAccess: searchParams.get('hasEaAccess') === 'true',
  })
}

function buildSearchParams(filters: CatalogFilterState, options: { filtersOpen?: boolean } = {}) {
  const next = new URLSearchParams()

  if (filters.sort && filters.sort !== 'popular') next.set('sort', filters.sort)
  if (filters.search) next.set('search', filters.search)
  if (filters.category) next.set('category', filters.category)
  if (filters.productKind && filters.productKind !== 'all') next.set('productKind', filters.productKind)
  if (filters.priceCurrency && filters.priceCurrency !== 'RUB') next.set('priceCurrency', filters.priceCurrency)
  if (filters.platform) next.set('platform', filters.platform)
  if (filters.players) next.set('players', filters.players)
  if (filters.gameLanguage) next.set('gameLanguage', filters.gameLanguage)
  if (filters.minPrice) next.set('minPrice', filters.minPrice)
  if (filters.maxPrice) next.set('maxPrice', filters.maxPrice)
  if (filters.hasDiscount) next.set('hasDiscount', 'true')
  if (filters.hasPsPlus) next.set('hasPsPlus', 'true')
  if (filters.hasEaAccess) next.set('hasEaAccess', 'true')
  if (options.filtersOpen) next.set('filters', 'open')

  return next
}

function areFiltersEqual(left: CatalogFilterState, right: CatalogFilterState) {
  return (
    left.page === right.page &&
    left.limit === right.limit &&
    left.sort === right.sort &&
    left.search === right.search &&
    left.category === right.category &&
    left.productKind === right.productKind &&
    left.priceCurrency === right.priceCurrency &&
    left.platform === right.platform &&
    left.players === right.players &&
    left.gameLanguage === right.gameLanguage &&
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
    filters.productKind !== 'all',
    filters.priceCurrency !== 'RUB',
    filters.platform,
    filters.players,
    filters.gameLanguage,
    filters.minPrice || filters.maxPrice,
    filters.hasDiscount,
    filters.hasPsPlus,
    filters.hasEaAccess,
  ].filter(Boolean).length
}

function mergeCatalogProducts(current: CatalogProduct[], next: CatalogProduct[]) {
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

function dedupeCatalogProducts(products: CatalogProduct[]) {
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

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const productKindStorageKey = useMemo(() => getProductKindStorageKey(user?.id), [user?.id])
  const storedProductKind = useMemo(() => readStoredProductKind(productKindStorageKey), [productKindStorageKey])
  const filters = useMemo(() => parseFilters(searchParams, storedProductKind), [searchParams, storedProductKind])
  const filtersKey = useMemo(() => buildSearchParams({ ...filters, page: 1 }).toString(), [filters])

  const [draftSearch, setDraftSearch] = useState(filters.search)
  const [draftFilters, setDraftFilters] = useState(filters)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [isFiltersOpen, setIsFiltersOpen] = useState(searchParams.get('filters') === 'open')
  const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false)
  const [products, setProducts] = useState<CatalogProduct[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [catalogNotice, setCatalogNotice] = useState<string | null>(null)
  const previousFiltersKeyRef = useRef(filtersKey)
  const loadMoreRef = useRef<HTMLDivElement | null>(null)
  const activeFiltersCount = countActiveFilters(filters)

  useEffect(() => {
    setDraftSearch(filters.search)
    setDraftFilters(filters)
  }, [filters])

  useEffect(() => {
    setIsFiltersOpen(searchParams.get('filters') === 'open')
  }, [searchParams])

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
      setSearchParams(buildSearchParams(normalizedFilters, { filtersOpen: searchParams.get('filters') === 'open' }), { replace: true })
    }
  }, [categories, filters, searchParams, setSearchParams])

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

    const nextParams = buildSearchParams(nextFilters, { filtersOpen: isFiltersOpen }).toString()
    const currentParams = buildSearchParams(currentFilters, { filtersOpen: isFiltersOpen }).toString()

    if (nextParams === currentParams) {
      return undefined
    }

    const timeoutId = window.setTimeout(() => {
      setSearchParams(buildSearchParams(nextFilters, { filtersOpen: isFiltersOpen }), { replace: true })
      persistProductKind(nextFilters.productKind)
    }, 1000)

    return () => window.clearTimeout(timeoutId)
  }, [draftFilters, draftSearch, filters, isFiltersOpen, productKindStorageKey, setSearchParams])

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
        const response = await fetchCatalog({
          page,
          limit: filters.limit,
          sort: filters.sort,
          search: filters.search || undefined,
          category: filters.category || undefined,
          product_kind: filters.productKind !== DEFAULT_FILTERS.productKind ? filters.productKind : undefined,
          price_currency: filters.priceCurrency || undefined,
          platform: filters.platform || undefined,
          players: filters.players || undefined,
          game_language: filters.gameLanguage || undefined,
          min_price: filters.minPrice ? Number(filters.minPrice) : undefined,
          max_price: filters.maxPrice ? Number(filters.maxPrice) : undefined,
          has_discount: filters.hasDiscount || undefined,
          has_ps_plus: filters.hasPsPlus || undefined,
          has_ea_access: filters.hasEaAccess || undefined,
          grouped: true,
        })

        if (!ignore) {
          setProducts((current) =>
            isFirstPage
              ? dedupeCatalogProducts(response.products)
              : mergeCatalogProducts(current, dedupeCatalogProducts(response.products)),
          )
          setTotal(response.total)
          setHasNextPage(response.hasNext)
          setCatalogNotice(null)
        }
      } catch {
        if (!ignore) {
          if (isFirstPage) {
            setProducts([])
            setTotal(0)
          }
          setHasNextPage(false)
          setCatalogNotice('Не удалось загрузить каталог. Попробуй обновить страницу или изменить фильтры чуть позже.')
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

  function updateDraftFilters(partial: Partial<CatalogFilterState>) {
    setDraftFilters((current) => ({
      ...current,
      ...partial,
    }))
  }

  function persistProductKind(productKind: string) {
    if (typeof window === 'undefined') {
      return
    }

    if (productKind && productKind !== DEFAULT_FILTERS.productKind) {
      window.localStorage.setItem(productKindStorageKey, productKind)
      return
    }

    window.localStorage.removeItem(productKindStorageKey)
  }

  function applyDraftFilters({ close = false } = {}) {
    const nextFilters = {
      ...draftFilters,
      search: draftSearch.trim(),
      page: 1,
      limit: DEFAULT_FILTERS.limit,
    }

    persistProductKind(nextFilters.productKind)
    setSearchParams(buildSearchParams(nextFilters, { filtersOpen: !close && isFiltersOpen }), { replace: true })

    if (close) {
      setIsFiltersOpen(false)
    }
  }

  function resetDraftFilters() {
    const nextFilters = {
      ...DEFAULT_FILTERS,
      page: 1,
      limit: filters.limit,
    }

    persistProductKind(nextFilters.productKind)
    setDraftSearch('')
    setDraftFilters(nextFilters)
    setSearchParams(buildSearchParams(nextFilters), { replace: true })
    setIsFiltersOpen(false)
    setIsMobileSearchOpen(false)
  }

  return (
    <div className="container pb-4 pt-6 md:pb-6 md:pt-8">
      <section className="sticky top-[5.75rem] z-30 rounded-[26px] border border-white/10 bg-gradient-to-br from-slate-950/95 via-slate-900/92 to-sky-950/76 p-3 shadow-[0_24px_80px_rgba(8,18,34,0.38)] ring-1 ring-brand-300/10 backdrop-blur-xl md:top-28 md:rounded-[32px] md:p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <label className={clsx('input-shell flex-1 shadow-[0_18px_50px_rgba(8,18,34,0.2)] sm:flex', isMobileSearchOpen ? 'flex' : 'hidden')}>
            <Search size={18} className="text-brand-300" />
            <input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Поиск игр и подписок..."
              className="w-full bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
            />
          </label>

          <div className="flex w-full items-center justify-end gap-2 sm:w-auto md:gap-3">
            <button
              type="button"
              onClick={() => setIsMobileSearchOpen((value) => !value)}
              className={clsx(
                'inline-flex min-h-[44px] shrink-0 items-center justify-center rounded-2xl border px-3 text-white transition sm:hidden',
                isMobileSearchOpen ? 'border-brand-300/50 bg-brand-500/20' : 'border-white/10 bg-white/5',
              )}
              aria-label="Открыть поиск"
              aria-pressed={isMobileSearchOpen}
            >
              <Search size={18} />
            </button>

            <div className="mr-auto rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 sm:mr-0 sm:w-auto md:px-4 md:text-sm">
              <span className="font-semibold text-white">{total}</span> товаров
              {activeFiltersCount > 0 ? `, фильтров: ${activeFiltersCount}` : ''}
            </div>

            <button type="button" onClick={() => setIsFiltersOpen((value) => !value)} className="btn-secondary">
              <SlidersHorizontal size={16} />
              Фильтр
              {activeFiltersCount > 0 ? (
                <span className="rounded-full bg-brand-400/20 px-2 py-0.5 text-xs text-brand-100">{activeFiltersCount}</span>
              ) : null}
            </button>
          </div>
        </div>

        {isFiltersOpen ? (
          <CatalogFilters
            categories={categories}
            draftFilters={draftFilters}
            onDraftChange={updateDraftFilters}
            onReset={resetDraftFilters}
            onApply={() => applyDraftFilters({ close: true })}
            className="mt-4"
          />
        ) : null}
      </section>

      {catalogNotice ? (
        <div className="mt-4 rounded-[22px] border border-amber-300/20 bg-amber-500/10 px-4 py-3 text-sm leading-7 text-amber-50">
          {catalogNotice}
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:mt-6 md:gap-4 lg:grid-cols-3 2xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: filters.limit }).map((_, index) => <ProductSkeleton key={index} />)
          : products.map((product) => <ProductCard key={`${product.id}-${product.region || 'all'}`} product={product} />)}
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
