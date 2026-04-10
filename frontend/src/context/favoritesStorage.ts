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

function getFavoriteTimestamp(entry: FavoriteEntry) {
  const timestamp = Date.parse(entry.addedAt)
  return Number.isFinite(timestamp) ? timestamp : 0
}

function mergeFavoritePair(existing: FavoriteEntry, incoming: FavoriteEntry) {
  if (getFavoriteTimestamp(incoming) >= getFavoriteTimestamp(existing)) {
    return {
      ...incoming,
      region: incoming.region ?? existing.region ?? null,
    }
  }

  return {
    ...existing,
    region: existing.region ?? incoming.region ?? null,
  }
}

export function createFavoriteEntry(payload: FavoriteTogglePayload, addedAt = new Date().toISOString()): FavoriteEntry {
  return {
    productId: payload.productId.trim(),
    region: normalizeRegion(payload.region),
    addedAt,
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

export function mergeFavoriteCollections(collections: FavoriteEntry[][]) {
  const merged = new Map<string, FavoriteEntry>()

  for (const collection of collections) {
    for (const entry of collection) {
      const currentEntry = merged.get(entry.productId)

      if (!currentEntry) {
        merged.set(entry.productId, entry)
        continue
      }

      merged.set(entry.productId, mergeFavoritePair(currentEntry, entry))
    }
  }

  return Array.from(merged.values())
}

export function addFavoriteEntry(entries: FavoriteEntry[], payload: FavoriteTogglePayload, addedAt?: string) {
  return mergeFavoriteCollections([entries, [createFavoriteEntry(payload, addedAt)]])
}

export function removeFavoriteEntry(entries: FavoriteEntry[], productId: string) {
  return entries.filter((entry) => entry.productId !== productId)
}

export function toggleFavoriteEntry(entries: FavoriteEntry[], payload: FavoriteTogglePayload) {
  const existingEntry = entries.find((entry) => entry.productId === payload.productId)

  if (existingEntry) {
    return removeFavoriteEntry(entries, payload.productId)
  }

  return addFavoriteEntry(entries, payload)
}
