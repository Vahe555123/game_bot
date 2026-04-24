import { describe, expect, it } from 'vitest'
import type { CatalogProduct, ProductRegionPrice } from '../types/catalog'
import {
  getEffectiveRegionalPrice,
  getBestLocalizationPresentation,
  getLocalizationPresentation,
  getProductLocalizationPresentation,
  getProductPsPlusSavingsPercent,
  getProductRegularDiscountPercent,
  getProductTitle,
  getVisibleRegionalPrices,
  shouldUsePsPlusPrice,
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

describe('getProductPsPlusSavingsPercent', () => {
  it('prefers the current route region when it has a PS Plus discount', () => {
    const product = buildProduct({
      routeRegion: 'IN',
      regionalPrices: [
        buildRegionalPrice('TR', 'РўСѓСЂС†РёСЏ', 1499, null, { psPlusDiscountPercent: 40 }),
        buildRegionalPrice('IN', 'РРЅРґРёСЏ', 1799, null, { psPlusDiscountPercent: 25 }),
      ],
    })

    expect(getProductPsPlusSavingsPercent(product)).toBe(25)
  })

  it('falls back to the highest PS Plus discount when the preferred region has none', () => {
    const product = buildProduct({
      routeRegion: 'UA',
      regionalPrices: [
        buildRegionalPrice('TR', 'РўСѓСЂС†РёСЏ', 1499, null, { psPlusDiscountPercent: 40 }),
        buildRegionalPrice('IN', 'РРЅРґРёСЏ', 1799, null, { psPlusDiscountPercent: 25 }),
      ],
    })

    expect(getProductPsPlusSavingsPercent(product)).toBe(40)
  })
})

describe('PS Plus pricing helpers', () => {
  it('switches to PS Plus price when it is cheaper than the regular one', () => {
    const price = buildRegionalPrice('TR', 'Турция', 1499, null, {
      priceLocal: 100,
      oldPriceLocal: 100,
      oldPriceRub: 1499,
      psPlusPriceLocal: 80,
      psPlusPriceRub: 1199,
      discountPercent: null,
      psPlusDiscountPercent: 20,
    })

    expect(shouldUsePsPlusPrice(price)).toBe(true)
    expect(getEffectiveRegionalPrice(price)).toMatchObject({
      isPsPlus: true,
      currentRub: 1199,
      oldRub: 1499,
      discountPercent: 20,
    })
  })

  it('keeps only regular discounts in the red sale badge helper', () => {
    const product = buildProduct({
      discountPercent: 20,
      regionalPrices: [
        buildRegionalPrice('TR', 'Турция', 1499, null, {
          discountPercent: null,
          psPlusDiscountPercent: 20,
        }),
      ],
    })

    expect(getProductRegularDiscountPercent(product)).toBeNull()
  })
})

describe('getLocalizationPresentation', () => {
  it('marks full Russian localization correctly', () => {
    const localization = getLocalizationPresentation('Полностью на русском')

    expect(localization.status).toBe('full')
    expect(localization.shortLabel).toBe('Полностью на русском')
  })

  it('marks partial Russian localization correctly', () => {
    const localization = getLocalizationPresentation('Русский интерфейс')

    expect(localization.status).toBe('partial')
    expect(localization.shortLabel).toBe('Русские субтитры')
  })

  it('marks missing Russian localization as unsupported', () => {
    const localization = getLocalizationPresentation('Нет русского языка')

    expect(localization.status).toBe('unsupported')
    expect(localization.shortLabel).toBe('Без русского')
  })
})

describe('getBestLocalizationPresentation', () => {
  it('prefers the best available Russian localization across regions', () => {
    const localization = getBestLocalizationPresentation([
      'Нет русского языка',
      'Русский интерфейс',
      'Полностью на русском',
    ])

    expect(localization.status).toBe('full')
    expect(localization.shortLabel).toBe('Полностью на русском')
  })
})

describe('getProductLocalizationPresentation', () => {
  it('uses regional localization when regions differ', () => {
    const product = buildProduct({
      localizationName: 'Без русского',
      regionalPrices: [
        buildRegionalPrice('TR', 'Турция', 1499, 'Нет русского языка'),
        buildRegionalPrice('IN', 'Индия', 1799, 'Нет русского языка'),
        buildRegionalPrice('UA', 'Украина', 1999, 'Полностью на русском'),
      ],
    })

    const localization = getProductLocalizationPresentation(product)

    expect(localization.status).toBe('full')
    expect(localization.shortLabel).toBe('Полностью на русском')
  })

  it('uses product localization when regional names are missing', () => {
    const product = buildProduct({
      localizationName: 'Русские субтитры',
      regionalPrices: [
        buildRegionalPrice('TR', 'Турция', 1499, null),
        buildRegionalPrice('IN', 'Индия', 1799, null),
      ],
    })

    const localization = getProductLocalizationPresentation(product)

    expect(localization.status).toBe('partial')
    expect(localization.shortLabel).toBe('Русские субтитры')
  })
})

describe('shouldShowOldPrice', () => {
  it('hides old price when product has no discount', () => {
    expect(
      shouldShowOldPrice({
        priceLocal: null,
        priceRub: 1516,
        oldPriceLocal: null,
        oldPriceRub: 1516,
        psPlusPriceLocal: null,
        psPlusPriceRub: null,
        discountPercent: null,
        psPlusDiscountPercent: null,
      }),
    ).toBe(false)
  })

  it('shows old price only when it is really higher than the current one', () => {
    expect(
      shouldShowOldPrice({
        priceLocal: null,
        priceRub: 1623,
        oldPriceLocal: null,
        oldPriceRub: 1723,
        psPlusPriceLocal: null,
        psPlusPriceRub: null,
        discountPercent: 6,
        psPlusDiscountPercent: null,
      }),
    ).toBe(true)
  })

  it('shows old price for PS Plus sales too', () => {
    expect(
      shouldShowOldPrice({
        priceLocal: 100,
        priceRub: 1623,
        oldPriceLocal: 100,
        oldPriceRub: 1723,
        psPlusPriceLocal: 80,
        psPlusPriceRub: 1400,
        discountPercent: null,
        psPlusDiscountPercent: 19,
      }),
    ).toBe(true)
  })
})

function buildRegionalPrice(
  region: string,
  name: string,
  priceRub: number,
  localizationName: string | null = null,
  overrides: Partial<ProductRegionPrice> = {},
): ProductRegionPrice {
  return {
    region,
    label: region,
    name,
    currencyCode: 'RUB',
    flag: null,
    available: true,
    priceLocal: null,
    oldPriceLocal: null,
    psPlusPriceLocal: null,
    priceRub,
    oldPriceRub: null,
    psPlusPriceRub: null,
    hasDiscount: false,
    discountPercent: null,
    psPlusDiscountPercent: null,
    localizationName,
    ...overrides,
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
    favoritesCount: 0,
    priceRub: null,
    oldPriceRub: null,
    displayPrice: null,
    displayOldPrice: null,
    regionalPrices: [],
    tags: [],
    compound: [],
    info: [],
    ...overrides,
  }
}
