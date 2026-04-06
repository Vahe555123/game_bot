import type { CatalogFilterState, CatalogProduct } from '../types/catalog'

export const REGION_OPTIONS = [
  { value: '', label: 'Все регионы' },
  { value: 'en-ua', label: 'Украина' },
  { value: 'en-tr', label: 'Турция' },
  { value: 'en-in', label: 'Индия' },
] as const

const REGION_OPTION_VALUES = new Set(REGION_OPTIONS.map((option) => option.value))

export const PLATFORM_OPTIONS = [
  { value: '', label: 'Все платформы' },
  { value: 'PS4_ALL', label: 'PS4' },
  { value: 'PS5_ALL', label: 'PS5' },
  { value: 'PS4_ONLY', label: 'Только PS4' },
  { value: 'PS5_ONLY', label: 'Только PS5' },
  { value: 'BOTH', label: 'PS4 + PS5' },
] as const

const PLATFORM_OPTION_VALUES = new Set(PLATFORM_OPTIONS.map((option) => option.value))

export const PLAYER_OPTIONS = [
  { value: '', label: 'Количество игроков' },
  { value: 'singleplayer', label: 'Одиночная игра' },
  { value: 'coop', label: 'Кооператив' },
] as const

const PLAYER_OPTION_VALUES = new Set(PLAYER_OPTIONS.map((option) => option.value))

export const SORT_OPTIONS = [
  { value: 'popular', label: 'Популярность' },
  { value: 'alphabet', label: 'По алфавиту' },
  { value: 'price_asc', label: 'По цене' },
] as const

const SORT_OPTION_VALUES = new Set(SORT_OPTIONS.map((option) => option.value))

const REGION_NORMALIZATION_MAP: Record<string, string> = {
  'en-ua': 'UA',
  'en-tr': 'TR',
  'en-in': 'IN',
  ua: 'UA',
  tr: 'TR',
  in: 'IN',
  uah: 'UA',
  try: 'TR',
  inr: 'IN',
}

export function normalizeRegionFilterValue(region?: string | null) {
  if (!region) {
    return ''
  }

  return REGION_NORMALIZATION_MAP[region.toLowerCase()] || region.toUpperCase()
}

function sanitizeSelectValue<T extends string>(value: string, allowedValues: ReadonlySet<T>): T | '' {
  return allowedValues.has(value as T) ? (value as T) : ''
}

function sanitizePriceValue(value: string) {
  if (!value) {
    return ''
  }

  const normalized = value.replace(',', '.').trim()
  const parsed = Number(normalized)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return ''
  }

  return String(parsed)
}

export function sanitizeCatalogFilters(filters: CatalogFilterState, categories: string[] = []): CatalogFilterState {
  const minPrice = sanitizePriceValue(filters.minPrice)
  const maxPrice = sanitizePriceValue(filters.maxPrice)
  const parsedMinPrice = minPrice ? Number(minPrice) : null
  const parsedMaxPrice = maxPrice ? Number(maxPrice) : null
  const hasInvalidRange =
    parsedMinPrice !== null && parsedMaxPrice !== null && Number.isFinite(parsedMinPrice) && Number.isFinite(parsedMaxPrice)
      ? parsedMinPrice > parsedMaxPrice
      : false

  return {
    ...filters,
    sort: sanitizeSelectValue(filters.sort, SORT_OPTION_VALUES) || 'popular',
    region: sanitizeSelectValue(filters.region, REGION_OPTION_VALUES),
    platform: sanitizeSelectValue(filters.platform, PLATFORM_OPTION_VALUES),
    players: sanitizeSelectValue(filters.players, PLAYER_OPTION_VALUES),
    category: !filters.category || !categories.length || categories.includes(filters.category) ? filters.category : '',
    minPrice: hasInvalidRange ? '' : minPrice,
    maxPrice: hasInvalidRange ? '' : maxPrice,
    search: filters.search.trim(),
  }
}

export function hasActiveCatalogFilters(filters: CatalogFilterState) {
  return Boolean(
    filters.category ||
      filters.region ||
      filters.platform ||
      filters.players ||
      filters.minPrice ||
      filters.maxPrice ||
      filters.hasDiscount ||
      filters.hasPsPlus ||
      filters.hasEaAccess,
  )
}

export function matchesPlatformFilter(product: CatalogProduct, platformFilter: string) {
  if (!platformFilter) {
    return true
  }

  const platforms = (product.platforms || '').toUpperCase()
  const hasPS4 = platforms.includes('PS4')
  const hasPS5 = platforms.includes('PS5')

  switch (platformFilter) {
    case 'PS4_ALL':
      return hasPS4
    case 'PS5_ALL':
      return hasPS5
    case 'PS4_ONLY':
    case 'PS4':
      return hasPS4 && !hasPS5
    case 'PS5_ONLY':
    case 'PS5':
      return hasPS5 && !hasPS4
    case 'BOTH':
      return hasPS4 && hasPS5
    default:
      return true
  }
}

export function matchesPlayersFilter(product: CatalogProduct, playersFilter: string) {
  if (!playersFilter) {
    return true
  }

  const minPlayers = product.playersMin ?? null
  const maxPlayers = product.playersMax ?? null

  if (playersFilter === 'singleplayer') {
    return minPlayers === 1 && (maxPlayers === null || maxPlayers === 1)
  }

  if (playersFilter === 'coop') {
    return typeof maxPlayers === 'number' ? maxPlayers > 1 : Boolean(product.playersOnline)
  }

  return true
}

export function matchesPriceRange(product: CatalogProduct, minPrice: string, maxPrice: string) {
  const price = product.priceRub

  if (price === null || price === undefined) {
    return !minPrice && !maxPrice
  }

  const min = minPrice ? Number(minPrice) : null
  const max = maxPrice ? Number(maxPrice) : null

  if (min !== null && !Number.isNaN(min) && price < min) {
    return false
  }

  if (max !== null && !Number.isNaN(max) && price > max) {
    return false
  }

  return true
}
