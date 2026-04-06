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
