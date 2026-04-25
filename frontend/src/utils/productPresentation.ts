import type { CatalogProduct, ProductRegionPrice } from '../types/catalog'
import { resolveRegionPresentation } from './format'

const REGION_SORT_ORDER: Record<string, number> = {
  TR: 0,
  IN: 1,
  UA: 2,
}

type LocalizationStatus = 'full' | 'partial' | 'unsupported' | 'unknown'

export type LocalizationPresentation = {
  status: LocalizationStatus
  shortLabel: string
  fullLabel: string
}

const LOCALIZATION_PRIORITY: Record<LocalizationStatus, number> = {
  full: 3,
  partial: 2,
  unsupported: 1,
  unknown: 0,
}

function compareRegionalPrices(left: ProductRegionPrice, right: ProductRegionPrice) {
  const leftOrder = REGION_SORT_ORDER[left.region] ?? Number.MAX_SAFE_INTEGER
  const rightOrder = REGION_SORT_ORDER[right.region] ?? Number.MAX_SAFE_INTEGER

  if (leftOrder !== rightOrder) {
    return leftOrder - rightOrder
  }

  return left.name.localeCompare(right.name, 'ru')
}

export function sortRegionalPrices(prices: ProductRegionPrice[]) {
  return [...prices].sort(compareRegionalPrices)
}

export function getVisibleRegionalPrices(product: CatalogProduct) {
  const sortedPrices = sortRegionalPrices(product.regionalPrices)

  if (sortedPrices.length > 0) {
    return sortedPrices
  }

  const fallbackRegionalPrices: ProductRegionPrice[] = [
    buildRegionalPriceFromProduct('TR', 'Турция', 'TRY', product.priceTry, product.oldPriceTry, product.psPlusPriceTry, product),
    buildRegionalPriceFromProduct('IN', 'Индия', 'INR', product.priceInr, product.oldPriceInr, product.psPlusPriceInr, product),
    buildRegionalPriceFromProduct('UA', 'Украина', 'UAH', product.priceUah, product.oldPriceUah, product.psPlusPriceUah, product),
  ].filter((price): price is ProductRegionPrice => Boolean(price))

  if (fallbackRegionalPrices.length > 0) {
    return sortRegionalPrices(fallbackRegionalPrices)
  }

  if (product.priceRub === null && product.oldPriceRub === null) {
    return []
  }

  const region = resolveRegionPresentation(product.region, product.regionInfo?.name)

  return [
    {
      region: product.region || region.label,
      label: region.label,
      name: region.name,
      currencyCode: product.regionInfo?.code || 'RUB',
      flag: null,
      available: true,
      priceLocal: null,
      oldPriceLocal: null,
      psPlusPriceLocal: null,
      priceRub: product.priceRub,
      oldPriceRub: product.oldPriceRub,
      psPlusPriceRub: null,
      hasDiscount: product.hasDiscount,
      discountPercent: product.discountPercent,
      psPlusDiscountPercent: null,
      localizationName: product.localizationName,
    },
  ]
}

function buildRegionalPriceFromProduct(
  region: string,
  name: string,
  currencyCode: string,
  priceLocal: number | null | undefined,
  oldPriceLocal: number | null | undefined,
  psPlusPriceLocal: number | null | undefined,
  product: Pick<CatalogProduct, 'localizationName' | 'hasDiscount' | 'discountPercent'>,
): ProductRegionPrice | null {
  const currentPrice = priceLocal ?? null
  const oldPrice = oldPriceLocal ?? null
  const psPlusPrice = psPlusPriceLocal ?? null

  if (currentPrice === null && oldPrice === null && psPlusPrice === null) {
    return null
  }

  const discountPercent =
    typeof currentPrice === 'number' &&
    typeof oldPrice === 'number' &&
    oldPrice > currentPrice &&
    oldPrice > 0
      ? Math.round(((oldPrice - currentPrice) / oldPrice) * 100)
      : null

  const psPlusDiscountPercent =
    typeof psPlusPrice === 'number' &&
    typeof oldPrice === 'number' &&
    oldPrice > psPlusPrice &&
    oldPrice > 0
      ? Math.round(((oldPrice - psPlusPrice) / oldPrice) * 100)
      : null

  return {
    region,
    label: region,
    name,
    currencyCode,
    flag: null,
    available: true,
    priceLocal: currentPrice,
    oldPriceLocal: oldPrice,
    psPlusPriceLocal: psPlusPrice,
    priceRub: null,
    oldPriceRub: null,
    psPlusPriceRub: null,
    hasDiscount: Boolean(discountPercent || psPlusDiscountPercent || product.hasDiscount),
    discountPercent: discountPercent ?? product.discountPercent ?? null,
    psPlusDiscountPercent,
    localizationName: product.localizationName ?? null,
  }
}

function normalizeRegionCode(value?: string | null) {
  return value?.trim().toUpperCase() || null
}

function isPositiveNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function getRegionalPsPlusSavingsPercent(
  price: Pick<
    ProductRegionPrice,
    | 'priceRub'
    | 'priceLocal'
    | 'oldPriceRub'
    | 'oldPriceLocal'
    | 'psPlusPriceRub'
    | 'psPlusPriceLocal'
    | 'psPlusDiscountPercent'
  >,
) {
  if (typeof price.psPlusDiscountPercent === 'number' && price.psPlusDiscountPercent > 0) {
    return price.psPlusDiscountPercent
  }

  const regularComparable = price.priceRub ?? price.priceLocal ?? price.oldPriceRub ?? price.oldPriceLocal
  const psPlusComparable = price.psPlusPriceRub ?? price.psPlusPriceLocal

  if (!isPositiveNumber(regularComparable) || !isPositiveNumber(psPlusComparable) || psPlusComparable >= regularComparable) {
    return null
  }

  return Math.round(((regularComparable - psPlusComparable) / regularComparable) * 100)
}

export function shouldUsePsPlusPrice(
  price: Pick<
    ProductRegionPrice,
    | 'priceLocal'
    | 'oldPriceLocal'
    | 'psPlusPriceLocal'
    | 'priceRub'
    | 'oldPriceRub'
    | 'psPlusPriceRub'
    | 'discountPercent'
    | 'psPlusDiscountPercent'
  >,
) {
  const psPlusComparable = price.psPlusPriceRub ?? price.psPlusPriceLocal
  if (!isPositiveNumber(psPlusComparable)) {
    return false
  }

  const regularComparable = price.priceRub ?? price.priceLocal
  if (!isPositiveNumber(regularComparable)) {
    return true
  }

  if (psPlusComparable < regularComparable) {
    return true
  }

  const oldComparable = price.oldPriceRub ?? price.oldPriceLocal
  if (
    isPositiveNumber(oldComparable) &&
    psPlusComparable < oldComparable &&
    (price.psPlusDiscountPercent ?? 0) > (price.discountPercent ?? 0)
  ) {
    return true
  }

  return false
}

export function getEffectiveRegionalPrice(
  price: Pick<
    ProductRegionPrice,
    | 'priceLocal'
    | 'oldPriceLocal'
    | 'psPlusPriceLocal'
    | 'priceRub'
    | 'oldPriceRub'
    | 'psPlusPriceRub'
    | 'discountPercent'
    | 'psPlusDiscountPercent'
  >,
) {
  const isPsPlus = shouldUsePsPlusPrice(price)

  return {
    isPsPlus,
    currentLocal: isPsPlus ? (price.psPlusPriceLocal ?? price.priceLocal) : price.priceLocal,
    currentRub: isPsPlus ? (price.psPlusPriceRub ?? price.priceRub) : price.priceRub,
    oldLocal: price.oldPriceLocal ?? null,
    oldRub: price.oldPriceRub ?? null,
    discountPercent: isPsPlus ? (price.psPlusDiscountPercent ?? price.discountPercent ?? null) : (price.discountPercent ?? null),
  }
}

export function getProductPsPlusSavingsPercent(
  product: Pick<CatalogProduct, 'regionalPrices' | 'routeRegion' | 'region'>,
) {
  const regionalPricesWithSavings = sortRegionalPrices(product.regionalPrices)
    .map((price) => ({
      region: normalizeRegionCode(price.region),
      savingsPercent: getRegionalPsPlusSavingsPercent(price),
    }))
    .filter((price): price is { region: string | null; savingsPercent: number } => typeof price.savingsPercent === 'number')

  if (!regionalPricesWithSavings.length) {
    return null
  }

  const preferredRegions = [product.routeRegion, product.region]
    .map((region) => normalizeRegionCode(region))
    .filter((region): region is string => Boolean(region))

  for (const preferredRegion of preferredRegions) {
    const matchedPrice = regionalPricesWithSavings.find(
      (price) => price.region === preferredRegion,
    )

    if (matchedPrice?.savingsPercent) {
      return matchedPrice.savingsPercent
    }
  }

  return regionalPricesWithSavings.reduce<number | null>((bestSavings, price) => {
    const currentSavings = price.savingsPercent ?? null

    if (currentSavings === null) {
      return bestSavings
    }

    if (bestSavings === null || currentSavings > bestSavings) {
      return currentSavings
    }

    return bestSavings
  }, null)
}

export function getProductRegularDiscountPercent(
  product: Pick<CatalogProduct, 'regionalPrices' | 'discountPercent'>,
) {
  const regionalDiscounts = product.regionalPrices
    .map((price) => price.discountPercent)
    .filter((discount): discount is number => typeof discount === 'number' && discount > 0)

  if (regionalDiscounts.length) {
    return Math.max(...regionalDiscounts)
  }

  if (product.regionalPrices.length) {
    return null
  }

  return typeof product.discountPercent === 'number' && product.discountPercent > 0 ? product.discountPercent : null
}

export function getProductTitle(product: Pick<CatalogProduct, 'name' | 'mainName' | 'edition'>) {
  const fullName = product.name?.trim()

  if (fullName) {
    return fullName
  }

  const mainName = product.mainName?.trim()
  const edition = product.edition?.trim()

  if (mainName && edition) {
    const normalizedMainName = mainName.toLowerCase()
    const normalizedEdition = edition.toLowerCase()

    if (!normalizedMainName.includes(normalizedEdition)) {
      return `${mainName} ${edition}`
    }
  }

  return mainName || 'Без названия'
}

export function getProductVrLabel(product: Pick<CatalogProduct, 'info'>) {
  const info = (product.info || []).join(' ').toUpperCase()
  if (!info) {
    return null
  }

  if (info.includes('VR2')) {
    return 'VR2'
  }

  if (
    info.includes('PS VR') ||
    info.includes('PSVR') ||
    info.includes('PLAYSTATION VR') ||
    info.includes('PS CAMERA')
  ) {
    return 'VR1'
  }

  return null
}

export function getLocalizationPresentation(localizationName?: string | null): LocalizationPresentation {
  const source = localizationName?.trim()

  if (!source) {
    return {
      status: 'unknown',
      shortLabel: 'Язык не указан',
      fullLabel: 'Локализация не указана',
    }
  }

  const normalized = source.toLowerCase()
  const hasRussianMarker = /рус|russian/.test(normalized)
  const explicitNoRussian = /нет русского языка|без русского языка|no russian/.test(normalized)
  const englishOnly = /english only|английский язык/.test(normalized)
  const fullRussian = /полностью на русском|full russian|russian audio|русская озвучка/.test(normalized)
  const partialRussian = /русские субтитры|русский интерфейс|russian subtitles|russian interface/.test(normalized)

  if (explicitNoRussian || (englishOnly && !hasRussianMarker)) {
    return {
      status: 'unsupported',
      shortLabel: 'Без русского',
      fullLabel: source,
    }
  }

  if (fullRussian) {
    return {
      status: 'full',
      shortLabel: 'Полностью на русском',
      fullLabel: source,
    }
  }

  if (partialRussian || hasRussianMarker) {
    return {
      status: 'partial',
      shortLabel: 'Русские субтитры',
      fullLabel: source,
    }
  }

  return {
    status: 'unknown',
    shortLabel: 'Язык не указан',
    fullLabel: source,
  }
}

export function getBestLocalizationPresentation(localizationNames: Array<string | null | undefined>): LocalizationPresentation {
  let best = getLocalizationPresentation(null)

  localizationNames.forEach((localizationName) => {
    const candidate = getLocalizationPresentation(localizationName)

    if (LOCALIZATION_PRIORITY[candidate.status] > LOCALIZATION_PRIORITY[best.status]) {
      best = candidate
    }
  })

  return best
}

export function getProductLocalizationPresentation(product: Pick<CatalogProduct, 'localizationName' | 'regionalPrices'>) {
  const localizationNames = [...product.regionalPrices.map((price) => price.localizationName), product.localizationName]

  return getBestLocalizationPresentation(localizationNames)
}

export function shouldShowOldPrice(
  price: Pick<
    ProductRegionPrice,
    'oldPriceRub' | 'priceRub' | 'oldPriceLocal' | 'priceLocal' | 'psPlusPriceRub' | 'psPlusPriceLocal' | 'discountPercent' | 'psPlusDiscountPercent'
  >,
) {
  const effectivePrice = getEffectiveRegionalPrice(price)
  const currentPrice = effectivePrice.currentRub ?? effectivePrice.currentLocal
  const oldPrice = effectivePrice.oldRub ?? effectivePrice.oldLocal

  if (oldPrice === null) {
    return false
  }

  if (currentPrice === null) {
    return true
  }

  return oldPrice > currentPrice
}
