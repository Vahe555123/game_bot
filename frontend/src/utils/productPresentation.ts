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

  if (product.priceRub === null && product.oldPriceRub === null) {
    return []
  }

  const region = resolveRegionPresentation(product.routeRegion || product.region, product.regionInfo?.name)

  return [
    {
      region: product.routeRegion || product.region || region.label,
      label: region.label,
      name: region.name,
      currencyCode: product.regionInfo?.code || 'RUB',
      flag: null,
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

export function shouldShowOldPrice(
  price: Pick<ProductRegionPrice, 'hasDiscount' | 'oldPriceRub' | 'priceRub' | 'oldPriceLocal' | 'priceLocal'>,
) {
  if (!price.hasDiscount) {
    return false
  }

  const currentPrice = price.priceRub ?? price.priceLocal
  const oldPrice = price.oldPriceRub ?? price.oldPriceLocal

  if (oldPrice === null) {
    return false
  }

  if (currentPrice === null) {
    return true
  }

  return oldPrice > currentPrice
}
