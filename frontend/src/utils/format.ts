const regionMap: Record<string, { label: string; name: string }> = {
  TR: { label: 'TR', name: 'Турция' },
  UA: { label: 'UA', name: 'Украина' },
  IN: { label: 'IN', name: 'Индия' },
}

export function formatCurrency(value?: number | null, currencyCode?: string) {
  if (value === null || value === undefined) {
    return 'Цена по запросу'
  }

  const currency = currencyCode || 'RUB'

  try {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(value)
  } catch {
    return `${value} ${currency}`
  }
}

export type DualCurrencyPriceDisplay = {
  primary: string
  secondary: string | null
}

export function getDualCurrencyPriceDisplay(
  localValue?: number | null,
  currencyCode?: string | null,
  rubValue?: number | null,
): DualCurrencyPriceDisplay {
  const normalizedCurrency = currencyCode?.toUpperCase() || null
  const hasDedicatedLocalPrice =
    localValue !== null &&
    localValue !== undefined &&
    normalizedCurrency !== null &&
    normalizedCurrency !== 'RUB'

  if (hasDedicatedLocalPrice) {
    return {
      primary: formatCurrency(localValue, normalizedCurrency),
      secondary: rubValue !== null && rubValue !== undefined ? formatCurrency(rubValue, 'RUB') : null,
    }
  }

  const primaryValue = rubValue ?? localValue

  return {
    primary: formatCurrency(primaryValue, rubValue !== null && rubValue !== undefined ? 'RUB' : normalizedCurrency || 'RUB'),
    secondary: null,
  }
}

export function formatDualCurrencyInline(
  localValue?: number | null,
  currencyCode?: string | null,
  rubValue?: number | null,
) {
  const display = getDualCurrencyPriceDisplay(localValue, currencyCode, rubValue)
  return display.secondary ? `${display.primary} / ${display.secondary}` : display.primary
}

export function formatRating(value?: number | null) {
  if (!value) return '0.0'
  return value.toFixed(1)
}

export function normalizeImageUrl(image?: string | null) {
  if (!image) return null
  if (image.startsWith('//')) return `https:${image}`
  return image
}

export function resolveRegionPresentation(region?: string | null, fallbackName?: string) {
  const safeRegion = (region || '').toUpperCase()
  return regionMap[safeRegion] || { label: safeRegion || 'ALL', name: fallbackName || 'Все регионы' }
}
