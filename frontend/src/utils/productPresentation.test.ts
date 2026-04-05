import { describe, expect, it } from 'vitest'
import type { CatalogProduct, ProductRegionPrice } from '../types/catalog'
import {
  getLocalizationPresentation,
  getProductTitle,
  getVisibleRegionalPrices,
  shouldShowOldPrice,
  sortRegionalPrices,
} from './productPresentation'

describe('sortRegionalPrices', () => {
  it('keeps miniapp region order TR, IN, UA', () => {
    const prices: ProductRegionPrice[] = [
      buildRegionalPrice('UA', 'Украина', 1999),
      buildRegionalPrice('TR', 'Турция', 1499),
      buildRegionalPrice('IN', 'Индия', 1799),
    ]

    expect(sortRegionalPrices(prices).map((item) => item.region)).toEqual(['TR', 'IN', 'UA'])
  })
})

describe('getVisibleRegionalPrices', () => {
  it('falls back to product-level price when grouped prices are absent', () => {
    const product = buildProduct({
      region: 'TR',
      routeRegion: 'TR',
      priceRub: 1499,
      oldPriceRub: 1799,
      regionalPrices: [],
    })

    const prices = getVisibleRegionalPrices(product)

    expect(prices).toHaveLength(1)
    expect(prices[0]?.region).toBe('TR')
    expect(prices[0]?.priceRub).toBe(1499)
    expect(prices[0]?.oldPriceRub).toBe(1799)
  })
})

describe('getProductTitle', () => {
  it('prefers the full product name like miniapp', () => {
    expect(
      getProductTitle({
        name: 'Far Cry 6 Deluxe Edition',
        mainName: 'Far Cry 6',
        edition: 'Deluxe Edition',
      }),
    ).toBe('Far Cry 6 Deluxe Edition')
  })

  it('falls back to main name plus edition when full name is absent', () => {
    expect(
      getProductTitle({
        name: null,
        mainName: 'Far Cry 6',
        edition: 'Game of the Year Edition',
      }),
    ).toBe('Far Cry 6 Game of the Year Edition')
  })
})

describe('getLocalizationPresentation', () => {
  it('marks Russian localization as supported', () => {
    expect(getLocalizationPresentation('Русская озвучка').status).toBe('supported')
  })

  it('marks missing Russian localization as unsupported', () => {
    const localization = getLocalizationPresentation('Нет русского языка')

    expect(localization.status).toBe('unsupported')
    expect(localization.shortLabel).toBe('Без русского')
  })
})

describe('shouldShowOldPrice', () => {
  it('hides old price when product has no discount', () => {
    expect(
      shouldShowOldPrice({
        hasDiscount: false,
        priceLocal: null,
        priceRub: 1516,
        oldPriceLocal: null,
        oldPriceRub: 1516,
      }),
    ).toBe(false)
  })

  it('shows old price only when it is really higher than the current one', () => {
    expect(
      shouldShowOldPrice({
        hasDiscount: true,
        priceLocal: null,
        priceRub: 1623,
        oldPriceLocal: null,
        oldPriceRub: 1723,
      }),
    ).toBe(true)
  })
})

function buildRegionalPrice(region: string, name: string, priceRub: number): ProductRegionPrice {
  return {
    region,
    label: region,
    name,
    currencyCode: 'RUB',
    flag: null,
    priceLocal: null,
    oldPriceLocal: null,
    psPlusPriceLocal: null,
    priceRub,
    oldPriceRub: null,
    psPlusPriceRub: null,
    hasDiscount: false,
    discountPercent: null,
    psPlusDiscountPercent: null,
    localizationName: null,
  }
}

function buildProduct(overrides: Partial<CatalogProduct>): CatalogProduct {
  return {
    id: 'product-id',
    name: 'Product name',
    mainName: 'Product name',
    category: null,
    region: null,
    routeRegion: null,
    type: null,
    image: null,
    platforms: null,
    publisher: null,
    rating: null,
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
    priceRub: null,
    oldPriceRub: null,
    displayPrice: 'Цена по запросу',
    displayOldPrice: null,
    regionalPrices: [],
    tags: [],
    compound: [],
    info: [],
    ...overrides,
  }
}
