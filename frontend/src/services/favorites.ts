import type { FavoriteEntry, FavoriteTogglePayload } from '../context/favoritesStorage'
import { createFavoriteEntry } from '../context/favoritesStorage'
import { apiClient } from './api'

type FavoriteApiEntry = {
  product_id: string
  region?: string | null
  added_at?: string | null
}

function mapFavoriteEntry(entry: FavoriteApiEntry): FavoriteEntry {
  return createFavoriteEntry(
    {
      productId: entry.product_id,
      region: entry.region ?? null,
    },
    entry.added_at ?? undefined,
  )
}

export async function listSiteFavorites() {
  const response = await apiClient.get<FavoriteApiEntry[]>('/site/favorites')
  return response.data.map(mapFavoriteEntry)
}

export async function addSiteFavorite(payload: FavoriteTogglePayload) {
  const response = await apiClient.post<FavoriteApiEntry>('/site/favorites', {
    product_id: payload.productId,
    region: payload.region ?? null,
  })
  return mapFavoriteEntry(response.data)
}

export async function removeSiteFavorite(productId: string) {
  await apiClient.delete(`/site/favorites/${encodeURIComponent(productId)}`)
}
