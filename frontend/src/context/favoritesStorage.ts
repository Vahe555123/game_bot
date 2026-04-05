export type FavoriteEntry = {
  productId: string
  region?: string | null
  addedAt: string
}

export type FavoriteTogglePayload = {
  productId: string
  region?: string | null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function normalizeRegion(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim().toUpperCase() : null
}

function normalizeAddedAt(value: unknown) {
  if (typeof value === 'string' && value.trim()) {
    return value
  }

  return new Date().toISOString()
}

function normalizeFavoriteEntry(value: unknown): FavoriteEntry | null {
  if (typeof value === 'string' && value.trim()) {
    return {
      productId: value.trim(),
      region: null,
      addedAt: new Date().toISOString(),
    }
  }

  if (!isRecord(value) || typeof value.productId !== 'string' || !value.productId.trim()) {
    return null
  }

  return {
    productId: value.productId.trim(),
    region: normalizeRegion(value.region),
    addedAt: normalizeAddedAt(value.addedAt),
  }
}

export function parseFavorites(rawValue: string | null) {
  if (!rawValue) {
    return []
  }

  try {
    const parsed = JSON.parse(rawValue)

    if (!Array.isArray(parsed)) {
      return []
    }

    const seen = new Set<string>()

    return parsed.reduce<FavoriteEntry[]>((entries, value) => {
      const entry = normalizeFavoriteEntry(value)

      if (!entry || seen.has(entry.productId)) {
        return entries
      }

      seen.add(entry.productId)
      entries.push(entry)
      return entries
    }, [])
  } catch {
    return []
  }
}

export function toggleFavoriteEntry(entries: FavoriteEntry[], payload: FavoriteTogglePayload) {
  const existingEntry = entries.find((entry) => entry.productId === payload.productId)

  if (existingEntry) {
    return entries.filter((entry) => entry.productId !== payload.productId)
  }

  return [
    ...entries,
    {
      productId: payload.productId,
      region: normalizeRegion(payload.region),
      addedAt: new Date().toISOString(),
    },
  ]
}
