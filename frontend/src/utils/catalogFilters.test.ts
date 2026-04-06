import { describe, expect, it } from 'vitest'
import type { CatalogProduct } from '../types/catalog'
import {
  matchesPlatformFilter,
  matchesPlayersFilter,
  matchesPriceRange,
  normalizeRegionFilterValue,
} from './catalogFilters'

const baseProduct: CatalogProduct = {
  id: 'product-1',
  name: 'Sample Game',
  mainName: 'Sample Game',
  category: 'Экшен',
  region: 'TR',
  routeRegion: 'TR',
  type: 'Game',
  image: null,
  platforms: 'PS5 / PS4',
  publisher: 'PlayStation',
  rating: 4.5,
  edition: null,
  description: null,
  localization: null,
  localizationName: null,
  hasDiscount: false,
  discount: null,
  discountPercent: null,
  discountEnd: null,
  hasPsPlus: false,
  hasEaAccess: false,
  hasPsPlusExtraDeluxe: false,
  psPlusCollection: null,
  regionInfo: null,
  favoritesCount: 0,
  priceRub: 1500,
  oldPriceRub: null,
  displayPrice: '1 500 ₽',
  displayOldPrice: null,
  regionalPrices: [],
  tags: [],
  compound: [],
  info: [],
  playersMin: 1,
  playersMax: 1,
  playersOnline: false,
}

describe('catalog filter helpers', () => {
  it('normalizes bot region values to backend region codes', () => {
    expect(normalizeRegionFilterValue('en-tr')).toBe('TR')
    expect(normalizeRegionFilterValue('en-ua')).toBe('UA')
    expect(normalizeRegionFilterValue('en-in')).toBe('IN')
  })

  it('matches the same platform logic as miniapp', () => {
    expect(matchesPlatformFilter(baseProduct, 'PS4_ALL')).toBe(true)
    expect(matchesPlatformFilter(baseProduct, 'PS5_ALL')).toBe(true)
    expect(matchesPlatformFilter(baseProduct, 'BOTH')).toBe(true)
    expect(matchesPlatformFilter(baseProduct, 'PS4_ONLY')).toBe(false)
    expect(matchesPlatformFilter(baseProduct, 'PS5_ONLY')).toBe(false)
  })

  it('detects coop and singleplayer from normalized player fields', () => {
    const coopProduct = {
      ...baseProduct,
      playersMin: 1,
      playersMax: 4,
      playersOnline: true,
    }
    const soloProduct = {
      ...baseProduct,
      playersMin: 1,
      playersMax: 1,
      playersOnline: false,
    }

    expect(matchesPlayersFilter(coopProduct, 'coop')).toBe(true)
    expect(matchesPlayersFilter(coopProduct, 'singleplayer')).toBe(false)
    expect(matchesPlayersFilter(soloProduct, 'singleplayer')).toBe(true)
  })

  it('applies price range in rubles', () => {
    expect(matchesPriceRange(baseProduct, '1000', '2000')).toBe(true)
    expect(matchesPriceRange(baseProduct, '1600', '')).toBe(false)
    expect(matchesPriceRange(baseProduct, '', '1400')).toBe(false)
  })
})
