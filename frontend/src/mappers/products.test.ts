import { describe, expect, it } from 'vitest'
import type { RawCatalogProduct } from '../types/catalog'
import { normalizeCatalogProduct } from './products'

describe('normalizeCatalogProduct', () => {
  it('uses grouped ruble price when current_price is absent', () => {
    const rawProduct: RawCatalogProduct = {
      id: 'grouped-product',
      main_name: 'Valentine Revolution',
      region: 'TR',
      current_price: null,
      price_with_currency: null,
      rub_price: 428.75,
      rub_price_old: 612.5,
      has_discount: true,
      regional_prices: [
        {
          region: 'TR',
          currency_code: 'TRY',
          price_local: 331,
          price_rub: 428.75,
          old_price_rub: 612.5,
          has_discount: true,
          discount_percent: 30,
        },
      ],
    }

    const product = normalizeCatalogProduct(rawProduct)

    expect(product.priceRub).toBe(428.75)
    expect(product.oldPriceRub).toBe(612.5)
    expect(product.regionalPrices[0]?.priceLocal).toBe(331)
    expect(product.displayPrice).toBe(formatRub(428.75))
    expect(product.displayOldPrice).toBe(formatRub(612.5))
  })

  it('falls back to the cheapest regional price on detail-like responses', () => {
    const rawProduct: RawCatalogProduct = {
      id: 'detail-product',
      main_name: 'Valentine Revolution',
      region: 'TR',
      rub_price: null,
      rub_price_old: null,
      regional_prices: [
        {
          region: 'IN',
          currency_code: 'INR',
          price_rub: 549.45,
          old_price_rub: 785.7,
          has_discount: true,
          discount_percent: 30,
        },
        {
          region: 'TR',
          currency_code: 'TRY',
          price_rub: 428.75,
          old_price_rub: 612.5,
          has_discount: true,
          discount_percent: 30,
        },
      ],
    }

    const product = normalizeCatalogProduct(rawProduct)

    expect(product.priceRub).toBe(428.75)
    expect(product.oldPriceRub).toBe(612.5)
    expect(product.displayPrice).toBe(formatRub(428.75))
    expect(product.displayOldPrice).toBe(formatRub(612.5))
    expect(product.regionalPrices).toHaveLength(2)
  })

  it('prefers PS Plus regional price for display when it is the active sale price', () => {
    const rawProduct: RawCatalogProduct = {
      id: 'ps-plus-sale',
      main_name: 'Planet of Lana II',
      region: 'TR',
      release_date: '2026-04-24',
      rub_price: 428.75,
      rub_price_old: 612.5,
      has_discount: true,
      regional_prices: [
        {
          region: 'TR',
          currency_code: 'TRY',
          price_local: 100,
          old_price_local: 100,
          ps_plus_price_local: 80,
          price_rub: 428.75,
          old_price_rub: 612.5,
          ps_plus_price_rub: 350,
          has_discount: true,
          discount_percent: null,
          ps_plus_discount_percent: 20,
        },
      ],
    }

    const product = normalizeCatalogProduct(rawProduct)

    expect(product.releaseDate).toBe('2026-04-24')
    expect(product.priceRub).toBe(350)
    expect(product.oldPriceRub).toBe(612.5)
    expect(product.displayPrice).toBe(formatRub(350))
    expect(product.displayOldPrice).toBe(formatRub(612.5))
  })
})

function formatRub(value: number) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(value)
}
