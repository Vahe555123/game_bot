import type {
  CatalogProduct,
  CatalogListResponse,
  ProductRegionPrice,
  RawCatalogListResponse,
  RawCatalogProduct,
  RawRegionalPrice,
  RegionInfo,
} from '../types/catalog'
import { formatCurrency } from '../utils/format'
import { getEffectiveRegionalPrice } from '../utils/productPresentation'

const regionMeta: Record<string, { code: string; symbol: string; name: string }> = {
  TR: { code: 'TRY', symbol: '₺', name: 'Турция' },
  UA: { code: 'UAH', symbol: '₴', name: 'Украина' },
  IN: { code: 'INR', symbol: '₹', name: 'Индия' },
}

function ensureStringArray(value?: string[] | null) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function normalizeRegionInfo(region?: string | null, regionInfo?: RegionInfo | null): RegionInfo | null {
  if (regionInfo?.code || regionInfo?.symbol || regionInfo?.name) {
    return regionInfo
  }

  const normalizedRegion = (region || '').toUpperCase()
  const fallback = regionMeta[normalizedRegion]

  if (!fallback) {
    return null
  }

  return fallback
}

function normalizeRegionalPrice(price: RawRegionalPrice): ProductRegionPrice {
  const normalizedRegion = (price.region || '').toUpperCase()
  const fallback = regionMeta[normalizedRegion]

  return {
    region: normalizedRegion,
    label: normalizedRegion || 'ALL',
    name: price.name || fallback?.name || 'Неизвестный регион',
    currencyCode: price.currency_code || fallback?.code || null,
    flag: price.flag || null,
    available: price.available !== false,
    priceLocal: price.price_local ?? null,
    oldPriceLocal: price.old_price_local ?? null,
    psPlusPriceLocal: price.ps_plus_price_local ?? null,
    priceRub: price.price_rub ?? null,
    oldPriceRub: price.old_price_rub ?? null,
    psPlusPriceRub: price.ps_plus_price_rub ?? null,
    hasDiscount: Boolean(price.has_discount),
    discountPercent: price.discount_percent ?? null,
    psPlusDiscountPercent: price.ps_plus_discount_percent ?? null,
    localizationName: price.localization_name ?? null,
  }
}

function buildFallbackRegionalPrice(
  region: 'TR' | 'IN' | 'UA',
  raw: RawCatalogProduct,
): ProductRegionPrice | null {
  const meta = regionMeta[region]
  if (!meta) {
    return null
  }

  const priceFieldMap = {
    TR: {
      price: raw.price_try ?? null,
      oldPrice: raw.old_price_try ?? null,
      psPlusPrice: raw.ps_plus_price_try ?? null,
    },
    IN: {
      price: raw.price_inr ?? null,
      oldPrice: raw.old_price_inr ?? null,
      psPlusPrice: raw.ps_plus_price_inr ?? null,
    },
    UA: {
      price: raw.price_uah ?? null,
      oldPrice: raw.old_price_uah ?? null,
      psPlusPrice: raw.ps_plus_price_uah ?? null,
    },
  } as const

  const priceData = priceFieldMap[region]
  const priceLocal = priceData.price
  const oldPriceLocal = priceData.oldPrice
  const psPlusPriceLocal = priceData.psPlusPrice

  if (
    priceLocal === null &&
    oldPriceLocal === null &&
    psPlusPriceLocal === null
  ) {
    return null
  }

  const discountPercent =
    typeof priceLocal === 'number' &&
    typeof oldPriceLocal === 'number' &&
    oldPriceLocal > priceLocal &&
    oldPriceLocal > 0
      ? Math.round(((oldPriceLocal - priceLocal) / oldPriceLocal) * 100)
      : null

  const psPlusDiscountPercent =
    typeof psPlusPriceLocal === 'number' &&
    typeof oldPriceLocal === 'number' &&
    oldPriceLocal > psPlusPriceLocal &&
    oldPriceLocal > 0
      ? Math.round(((oldPriceLocal - psPlusPriceLocal) / oldPriceLocal) * 100)
      : null

  return {
    region,
    label: region,
    name: meta.name,
    currencyCode: meta.code,
    flag: null,
    available: true,
    priceLocal,
    oldPriceLocal,
    psPlusPriceLocal,
    priceRub: null,
    oldPriceRub: null,
    psPlusPriceRub: null,
    hasDiscount: Boolean(discountPercent || psPlusDiscountPercent),
    discountPercent,
    psPlusDiscountPercent,
    // Региональная локализация известна только когда backend кладёт её в regional_prices.
    // Глобальный raw.localization_name — это язык UA-записи; нельзя подставлять его в TR/IN
    // (баг: после обновления цен у Far Cry/GoW/AC Origins TR/IN показывали UA-локализацию).
    localizationName: null,
  }
}

function mergeRegionalPrice(
  existing: ProductRegionPrice,
  fallback: ProductRegionPrice,
): ProductRegionPrice {
  return {
    ...fallback,
    ...existing,
    flag: existing.flag ?? fallback.flag,
    currencyCode: existing.currencyCode ?? fallback.currencyCode,
    available: existing.available || fallback.available,
    priceLocal: existing.priceLocal ?? fallback.priceLocal,
    oldPriceLocal: existing.oldPriceLocal ?? fallback.oldPriceLocal,
    psPlusPriceLocal: existing.psPlusPriceLocal ?? fallback.psPlusPriceLocal,
    priceRub: existing.priceRub ?? fallback.priceRub,
    oldPriceRub: existing.oldPriceRub ?? fallback.oldPriceRub,
    psPlusPriceRub: existing.psPlusPriceRub ?? fallback.psPlusPriceRub,
    hasDiscount: existing.hasDiscount || fallback.hasDiscount,
    discountPercent: existing.discountPercent ?? fallback.discountPercent,
    psPlusDiscountPercent: existing.psPlusDiscountPercent ?? fallback.psPlusDiscountPercent,
    // Не фоллбэчим локализацию: если бэк не вернул её для данного региона — у этого
    // региона её действительно нет. Показываем "Язык не указан" (LocalizationBadge).
    localizationName: existing.localizationName,
  }
}

function resolveRegionalPrices(raw: RawCatalogProduct) {
  const mappedPrices = (raw.regional_prices || []).map(normalizeRegionalPrice)
  const priceMap = new Map(mappedPrices.map((price) => [price.region, price]))

  ;(['TR', 'IN', 'UA'] as const).forEach((region) => {
    const fallbackPrice = buildFallbackRegionalPrice(region, raw)
    if (!fallbackPrice) {
      return
    }

    const existingPrice = priceMap.get(region)
    priceMap.set(region, existingPrice ? mergeRegionalPrice(existingPrice, fallbackPrice) : fallbackPrice)
  })

  return Array.from(priceMap.values())
}

function pickPrimaryRegionalPrice(regionalPrices: ProductRegionPrice[]) {
  return regionalPrices
    .filter((price) => price.available && (typeof price.priceRub === 'number' || typeof price.psPlusPriceRub === 'number'))
    .sort((left, right) => {
      const leftEffective = getEffectiveRegionalPrice(left)
      const rightEffective = getEffectiveRegionalPrice(right)
      const leftPrice = leftEffective.currentRub ?? left.priceRub ?? Number.POSITIVE_INFINITY
      const rightPrice = rightEffective.currentRub ?? right.priceRub ?? Number.POSITIVE_INFINITY
      return leftPrice - rightPrice
    })[0]
}

function resolveDisplayPrice(raw: RawCatalogProduct, regionInfo: RegionInfo | null, primaryRegionalPrice?: ProductRegionPrice) {
  const effectiveRegionalPrice = primaryRegionalPrice ? getEffectiveRegionalPrice(primaryRegionalPrice) : null
  const hasRubPrice =
    effectiveRegionalPrice?.currentRub !== null && effectiveRegionalPrice?.currentRub !== undefined
      ? true
      : raw.rub_price !== null && raw.rub_price !== undefined
        ? true
        : raw.min_price_rub !== null && raw.min_price_rub !== undefined
          ? true
          : primaryRegionalPrice?.priceRub !== null && primaryRegionalPrice?.priceRub !== undefined
  const fallbackPrice =
    effectiveRegionalPrice?.currentRub ??
    raw.rub_price ??
    raw.min_price_rub ??
    primaryRegionalPrice?.priceRub ??
    raw.current_price ??
    raw.price ??
    null

  const fallbackOldPrice =
    effectiveRegionalPrice?.oldRub ??
    raw.rub_price_old ??
    primaryRegionalPrice?.oldPriceRub ??
    raw.old_price ??
    null

  const displayPrice =
    raw.price_with_currency?.trim() ||
    (fallbackPrice !== null
      ? formatCurrency(fallbackPrice, hasRubPrice ? 'RUB' : regionInfo?.code)
      : null)

  const displayOldPrice =
    fallbackOldPrice !== null
      ? formatCurrency(
          fallbackOldPrice,
          raw.rub_price_old || primaryRegionalPrice?.oldPriceRub ? 'RUB' : regionInfo?.code,
        )
      : null

  return {
    priceRub: effectiveRegionalPrice?.currentRub ?? raw.rub_price ?? raw.min_price_rub ?? primaryRegionalPrice?.priceRub ?? null,
    oldPriceRub: effectiveRegionalPrice?.oldRub ?? raw.rub_price_old ?? primaryRegionalPrice?.oldPriceRub ?? null,
    displayPrice,
    displayOldPrice,
  }
}

export function normalizeCatalogProduct(raw: RawCatalogProduct): CatalogProduct {
  const regionalPrices = resolveRegionalPrices(raw)
  const primaryRegionalPrice = pickPrimaryRegionalPrice(regionalPrices)
  const regionInfo = normalizeRegionInfo(raw.region, raw.region_info)
  const price = resolveDisplayPrice(raw, regionInfo, primaryRegionalPrice)

  return {
    id: raw.id,
    name: raw.name ?? null,
    mainName: raw.main_name || raw.name || 'Без названия',
    category: raw.category ?? null,
    region: raw.region ?? null,
    routeRegion: null, // Убираем routeRegion, так как он вызывает проблемы с URL
    type: raw.type ?? null,
    image: raw.image ?? null,
    platforms: raw.platforms ?? null,
    publisher: raw.publisher ?? null,
    rating: raw.rating ?? null,
    releaseDate: raw.release_date ?? null,
    edition: raw.edition ?? null,
    description: raw.description ?? null,
    localization: raw.localization ?? null,
    localizationName: raw.localization_name ?? primaryRegionalPrice?.localizationName ?? null,
    hasDiscount: Boolean(raw.has_discount),
    discount: raw.discount ?? null,
    discountPercent: raw.discount_percent ?? primaryRegionalPrice?.discountPercent ?? null,
    discountEnd: raw.discount_end ?? null,
    hasPsPlus: Boolean(raw.has_ps_plus),
    hasEaAccess: Boolean(raw.has_ea_access),
    hasPsPlusExtraDeluxe: Boolean(raw.has_ps_plus_extra_deluxe),
    psPlusCollection: raw.ps_plus_collection ?? null,
    regionInfo,
    favoritesCount: raw.favorites_count ?? 0,
    priceRub: price.priceRub,
    oldPriceRub: price.oldPriceRub,
    displayPrice: price.displayPrice,
    displayOldPrice: price.displayOldPrice,
    regionalPrices,
    priceTry: raw.price_try ?? null,
    oldPriceTry: raw.old_price_try ?? null,
    psPlusPriceTry: raw.ps_plus_price_try ?? null,
    priceInr: raw.price_inr ?? null,
    oldPriceInr: raw.old_price_inr ?? null,
    psPlusPriceInr: raw.ps_plus_price_inr ?? null,
    priceUah: raw.price_uah ?? null,
    oldPriceUah: raw.old_price_uah ?? null,
    psPlusPriceUah: raw.ps_plus_price_uah ?? null,
    tags: ensureStringArray(raw.tags),
    compound: ensureStringArray(raw.compound),
    info: ensureStringArray(raw.info),
    playersMin: raw.players_min ?? null,
    playersMax: raw.players_max ?? null,
    playersOnline: Boolean(raw.players_online),
  }
}

export function normalizeCatalogResponse(response: RawCatalogListResponse): CatalogListResponse {
  return {
    products: response.products.map(normalizeCatalogProduct),
    total: response.total,
    page: response.page,
    limit: response.limit,
    hasNext: response.has_next,
  }
}
