import { Search, SlidersHorizontal } from 'lucide-react'
import type { FormEvent } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CatalogFilters } from '../components/catalog/CatalogFilters'
import { ProductCard } from '../components/catalog/ProductCard'
import { ProductSkeleton } from '../components/catalog/ProductSkeleton'
import { SectionHeader } from '../components/common/SectionHeader'
import { mockProducts } from '../data/mockProducts'
import { fetchCatalog, fetchCategories } from '../services/catalog'
import type { CatalogFilterState, CatalogProduct } from '../types/catalog'
import {
  matchesPlatformFilter,
  matchesPlayersFilter,
  matchesPriceRange,
  normalizeRegionFilterValue,
} from '../utils/catalogFilters'

const DEFAULT_FILTERS: CatalogFilterState = {
  page: 1,
  limit: 12,
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

  return {
    ...DEFAULT_FILTERS,
    page: Number.isFinite(pageValue) && pageValue > 0 ? pageValue : 1,
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
  }
}

function applyMockFilters(products: CatalogProduct[], filters: CatalogFilterState) {
  const normalizedRegion = normalizeRegionFilterValue(filters.region)

  const filtered = products.filter((product) => {
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

  const start = (filters.page - 1) * filters.limit
  const end = start + filters.limit

  return {
    products: filtered.slice(start, end),
    total: filtered.length,
  }
}

function buildSearchParams(filters: CatalogFilterState) {
  const next = new URLSearchParams()

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
  if (filters.page > 1) next.set('page', String(filters.page))

  return next
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

export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(searchParams), [searchParams])

  const [draftSearch, setDraftSearch] = useState(filters.search)
  const [draftFilters, setDraftFilters] = useState(filters)
  const [isLoading, setIsLoading] = useState(true)
  const [isMobileFiltersOpen, setIsMobileFiltersOpen] = useState(false)
  const [products, setProducts] = useState<CatalogProduct[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [total, setTotal] = useState(0)

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
    let ignore = false
    setIsLoading(true)

    ;(async () => {
      try {
        const response = await fetchCatalog({
          page: filters.page,
          limit: filters.limit,
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
        })

        if (!ignore) {
          setProducts(response.products)
          setTotal(response.total)
        }
      } catch {
        if (!ignore) {
          const fallback = applyMockFilters(mockProducts, filters)
          setProducts(fallback.products)
          setTotal(fallback.total)
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [filters])

  const totalPages = Math.max(1, Math.ceil(total / filters.limit))
  const activeFiltersCount = countActiveFilters(filters)

  function updateDraftFilters(partial: Partial<CatalogFilterState>) {
    setDraftFilters((current) => ({
      ...current,
      ...partial,
    }))
  }

  function commitFilters(nextFilters: CatalogFilterState) {
    setSearchParams(buildSearchParams(nextFilters))
  }

  function applyDraftFilters() {
    const nextFilters = {
      ...draftFilters,
      search: draftSearch.trim(),
      page: 1,
    }

    setDraftFilters(nextFilters)
    commitFilters(nextFilters)
    setIsMobileFiltersOpen(false)
  }

  function resetDraftFilters() {
    const nextFilters = {
      ...DEFAULT_FILTERS,
      search: draftSearch.trim(),
      page: 1,
      limit: filters.limit,
    }

    setDraftFilters(nextFilters)
    commitFilters(nextFilters)
    setIsMobileFiltersOpen(false)
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const nextFilters = {
      ...filters,
      search: draftSearch.trim(),
      page: 1,
    }

    commitFilters(nextFilters)
  }

  return (
    <div className="container py-10 md:py-14">
      <SectionHeader
        eyebrow="Каталог"
        title="Каталог сайта в логике miniapp"
        description="Фильтры, значения и параметры запроса теперь повторяют miniapp: категории, регион, платформа, игроки, цена, скидки, PS Plus и EA Access."
        action={
          <button
            type="button"
            onClick={() => setIsMobileFiltersOpen((value) => !value)}
            className="btn-secondary md:hidden"
          >
            <SlidersHorizontal size={16} />
            Фильтры
          </button>
        }
      />

      <div className="mt-8 flex flex-col gap-8 lg:flex-row">
        <CatalogFilters
          categories={categories}
          draftFilters={draftFilters}
          onDraftChange={updateDraftFilters}
          onApply={applyDraftFilters}
          onReset={resetDraftFilters}
          className={`${isMobileFiltersOpen ? 'block' : 'hidden'} lg:block lg:w-[320px]`}
        />

        <div className="min-w-0 flex-1 space-y-6">
          <div className="panel-soft rounded-[28px] p-4 md:p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <form className="input-shell flex-1" onSubmit={submitSearch}>
                <Search size={18} className="text-brand-300" />
                <input
                  value={draftSearch}
                  onChange={(event) => setDraftSearch(event.target.value)}
                  placeholder="Поиск игр..."
                  className="w-full bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
                />
                <button type="submit" className="rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-white">
                  Найти
                </button>
              </form>

              <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
                {activeFiltersCount > 0 ? `Активных фильтров: ${activeFiltersCount}` : 'Фильтры не выбраны'}
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-2 text-sm text-slate-400 md:flex-row md:items-center md:justify-between">
              <p>
                Найдено <span className="font-semibold text-white">{total}</span> товаров
              </p>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {isLoading
              ? Array.from({ length: 6 }).map((_, index) => <ProductSkeleton key={index} />)
              : products.map((product) => <ProductCard key={`${product.id}-${product.region || 'all'}`} product={product} />)}
          </div>

          {!isLoading && products.length === 0 ? (
            <div className="panel-soft rounded-[28px] px-6 py-12 text-center text-slate-300">
              По этим параметрам товаров пока не нашлось. Попробуй изменить фильтры или очистить диапазон цен.
            </div>
          ) : null}

          <div className="flex flex-col gap-4 rounded-[28px] border border-white/10 bg-white/[0.04] p-4 md:flex-row md:items-center md:justify-between">
            <div className="text-sm text-slate-400">
              Страница <span className="font-semibold text-white">{filters.page}</span> из{' '}
              <span className="font-semibold text-white">{totalPages}</span>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => commitFilters({ ...filters, page: Math.max(1, filters.page - 1) })}
                disabled={filters.page <= 1}
                className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
              >
                Назад
              </button>
              <button
                type="button"
                onClick={() => commitFilters({ ...filters, page: Math.min(totalPages, filters.page + 1) })}
                disabled={filters.page >= totalPages}
                className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                Дальше
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
