import { normalizeCatalogProduct, normalizeCatalogResponse } from '../mappers/products'
import type { CatalogQuery, RawCatalogProduct, RawCatalogListResponse } from '../types/catalog'
import { apiClient } from './api'

function compactParams(params: CatalogQuery) {
  return Object.fromEntries(
    Object.entries(params).filter(([key, value]) => value !== undefined && value !== '' && (value !== false || key === 'grouped')),
  )
}

export async function fetchCatalog(params: CatalogQuery = {}) {
  const response = await apiClient.get<RawCatalogListResponse>('/products/', {
    params: compactParams(params),
  })

  return normalizeCatalogResponse(response.data)
}

export async function fetchCategories() {
  const response = await apiClient.get<string[]>('/products/categories/list')
  return response.data
}

export async function fetchProduct(productId: string, region?: string) {
  const response = await apiClient.get<RawCatalogProduct>(`/products/${productId}`, {
    params: compactParams({ region }),
  })

  return normalizeCatalogProduct(response.data)
}

export async function fetchProductsBatch(productIds: string[]) {
  const normalizedIds = Array.from(
    new Set(
      productIds
        .map((productId) => productId.trim())
        .filter(Boolean)
        .slice(0, 20),
    ),
  )

  if (!normalizedIds.length) {
    return normalizeCatalogResponse({
      products: [],
      total: 0,
      page: 1,
      limit: 0,
      has_next: false,
    })
  }

  const response = await apiClient.post<RawCatalogListResponse>('/products/batch', {
    product_ids: normalizedIds,
  })

  return normalizeCatalogResponse(response.data)
}
