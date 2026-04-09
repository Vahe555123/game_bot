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
import { getBestLocalizationPresentation } from '../utils/productPresentation'

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

function pickPrimaryRegionalPrice(regionalPrices: ProductRegionPrice[]) {
  return regionalPrices
    .filter((price) => typeof price.priceRub === 'number')
    .sort((left, right) => (left.priceRub ?? Number.POSITIVE_INFINITY) - (right.priceRub ?? Number.POSITIVE_INFINITY))[0]
}

function resolveDisplayPrice(raw: RawCatalogProduct, regionInfo: RegionInfo | null, primaryRegionalPrice?: ProductRegionPrice) {
  const fallbackPrice =
    raw.rub_price ??
    raw.min_price_rub ??
    primaryRegionalPrice?.priceRub ??
    raw.current_price ??
    raw.price ??
    null

  const fallbackOldPrice =
    raw.rub_price_old ??
    primaryRegionalPrice?.oldPriceRub ??
    raw.old_price ??
    null

  const displayPrice =
    raw.price_with_currency?.trim() ||
    (fallbackPrice !== null
      ? formatCurrency(fallbackPrice, raw.rub_price || raw.min_price_rub || primaryRegionalPrice?.priceRub ? 'RUB' : regionInfo?.code)
      : 'Цена по запросу')

  const displayOldPrice =
    fallbackOldPrice !== null
      ? formatCurrency(
          fallbackOldPrice,
          raw.rub_price_old || primaryRegionalPrice?.oldPriceRub ? 'RUB' : regionInfo?.code,
        )
      : null

  return {
    priceRub: raw.rub_price ?? raw.min_price_rub ?? primaryRegionalPrice?.priceRub ?? null,
    oldPriceRub: raw.rub_price_old ?? primaryRegionalPrice?.oldPriceRub ?? null,
    displayPrice,
    displayOldPrice,
  }
}

export function normalizeCatalogProduct(raw: RawCatalogProduct): CatalogProduct {
  const regionalPrices = (raw.regional_prices || []).map(normalizeRegionalPrice)
  const primaryRegionalPrice = pickPrimaryRegionalPrice(regionalPrices)
  const regionInfo = normalizeRegionInfo(raw.region, raw.region_info)
  const price = resolveDisplayPrice(raw, regionInfo, primaryRegionalPrice)
  const aggregatedLocalization = regionalPrices.length
    ? getBestLocalizationPresentation(regionalPrices.map((item) => item.localizationName))
    : null

  return {
    id: raw.id,
    name: raw.name ?? null,
    mainName: raw.main_name || raw.name || 'Без названия',
    category: raw.category ?? null,
    region: raw.region ?? null,
    routeRegion: raw.region ?? primaryRegionalPrice?.region ?? null,
    type: raw.type ?? null,
    image: raw.image ?? null,
    platforms: raw.platforms ?? null,
    publisher: raw.publisher ?? null,
    rating: raw.rating ?? null,
    edition: raw.edition ?? null,
    description: raw.description ?? null,
    localization: raw.localization ?? null,
    localizationName:
      aggregatedLocalization && aggregatedLocalization.status !== 'unknown'
        ? aggregatedLocalization.shortLabel
        : raw.localization_name ?? primaryRegionalPrice?.localizationName ?? null,
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
