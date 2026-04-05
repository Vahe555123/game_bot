import type { CatalogFilterState, CatalogProduct } from '../types/catalog'

export const REGION_OPTIONS = [
  { value: '', label: 'Все регионы' },
  { value: 'en-ua', label: '🇺🇦 Украина' },
  { value: 'en-tr', label: '🇹🇷 Турция' },
  { value: 'en-in', label: '🇮🇳 Индия' },
] as const

export const PLATFORM_OPTIONS = [
  { value: '', label: 'Все платформы' },
  { value: 'PS4_ALL', label: '🎮 PS4' },
  { value: 'PS5_ALL', label: '🎮 PS5' },
  { value: 'PS4_ONLY', label: '🎮 Только PS4' },
  { value: 'PS5_ONLY', label: '🎮 Только PS5' },
  { value: 'BOTH', label: '🎮 PS4 + PS5' },
] as const

export const PLAYER_OPTIONS = [
  { value: '', label: 'Количество игроков' },
  { value: 'singleplayer', label: '👤 Одиночная игра' },
  { value: 'coop', label: '🤝 Кооператив' },
] as const

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

  const infoText = product.info.join(' ').toLowerCase()

  if (playersFilter === 'singleplayer') {
    const hasSinglePlayer = infoText.includes('1 игрок')
    const hasCoopPattern = infoText.includes('игроки:')
    return hasSinglePlayer && !hasCoopPattern
  }

  if (playersFilter === 'coop') {
    return (
      infoText.includes('игроки: 1 - 2') ||
      infoText.includes('игроки: 2 - 4') ||
      infoText.includes('игроки: 1 - 4') ||
      infoText.includes('игроки: 2 - 8')
    )
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
