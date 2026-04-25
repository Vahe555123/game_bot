import type {
  AdminDashboard,
  AdminDiscountUpdateStatus,
  AdminHelpContent,
  AdminHelpContentPayload,
  AdminPriceUpdateStatus,
  AdminProductDetails,
  AdminProductListResponse,
  AdminProductManualParsePayload,
  AdminProductManualParseStartResponse,
  AdminProductManualParseStatusResponse,
  AdminProductPayload,
  AdminPurchase,
  AdminPurchaseFulfillPayload,
  AdminPurchaseListResponse,
  AdminPurchaseUpdatePayload,
  AdminUser,
  AdminUserListResponse,
  AdminUserPayload,
} from '../types/admin'
import { apiClient } from './api'

export async function fetchAdminDashboard() {
  const response = await apiClient.get<AdminDashboard>('/site/admin/dashboard')
  return response.data
}

export async function fetchAdminHelpContent() {
  const response = await apiClient.get<AdminHelpContent>('/site/admin/content/help')
  return response.data
}

export async function updateAdminHelpContent(payload: AdminHelpContentPayload) {
  const response = await apiClient.put<AdminHelpContent>('/site/admin/content/help', payload)
  return response.data
}

export async function fetchAdminUsers(params: {
  page?: number
  limit?: number
  search?: string
  role?: string
  is_active?: boolean
}) {
  const response = await apiClient.get<AdminUserListResponse>('/site/admin/users', { params })
  return response.data
}

export async function createAdminUser(payload: AdminUserPayload) {
  const response = await apiClient.post<AdminUser>('/site/admin/users', payload)
  return response.data
}

export async function updateAdminUser(userId: string, payload: AdminUserPayload) {
  const response = await apiClient.put<AdminUser>(`/site/admin/users/${userId}`, payload)
  return response.data
}

export async function deleteAdminUser(userId: string) {
  const response = await apiClient.delete<{ message: string }>(`/site/admin/users/${userId}`)
  return response.data
}

export async function fetchAdminProducts(params: {
  page?: number
  limit?: number
  search?: string
  region?: string
  category?: string
  sort?: string
  missing_region?: string
  // '' / 'any' / 'UA' / 'TR' / 'IN' — фильтр "язык не указан" по всему товару или конкретному региону.
  missing_localization?: string
}) {
  const response = await apiClient.get<AdminProductListResponse>('/site/admin/products', { params })
  return response.data
}

export async function fetchAdminDiscountProducts(params: {
  page?: number
  limit?: number
  search?: string
  region?: string
}) {
  const response = await apiClient.get<AdminProductListResponse>('/site/admin/discounts/products', { params })
  return response.data
}

export async function startAdminDiscountUpdate(test: boolean) {
  const response = await apiClient.post<AdminDiscountUpdateStatus>(
    '/site/admin/discounts/update',
    undefined,
    {
      params: { test },
      timeout: 0,
    },
  )
  return response.data
}

export async function fetchAdminDiscountUpdateStatus() {
  const response = await apiClient.get<AdminDiscountUpdateStatus>('/site/admin/discounts/update/status')
  return response.data
}

export async function pauseAdminDiscountUpdate() {
  const response = await apiClient.post<AdminDiscountUpdateStatus>('/site/admin/discounts/update/pause')
  return response.data
}

export async function resumeAdminDiscountUpdate() {
  const response = await apiClient.post<AdminDiscountUpdateStatus>('/site/admin/discounts/update/resume')
  return response.data
}

export async function cancelAdminDiscountUpdate() {
  const response = await apiClient.post<AdminDiscountUpdateStatus>('/site/admin/discounts/update/cancel')
  return response.data
}

// ── Обновление цен ──────────────────────────────────────────────────────────
export async function startAdminPriceUpdate(test: boolean) {
  const response = await apiClient.post<AdminPriceUpdateStatus>(
    '/site/admin/prices/update',
    undefined,
    { params: { test }, timeout: 0 },
  )
  return response.data
}

export async function fetchAdminPriceUpdateStatus() {
  const response = await apiClient.get<AdminPriceUpdateStatus>('/site/admin/prices/update/status')
  return response.data
}

export async function pauseAdminPriceUpdate() {
  const response = await apiClient.post<AdminPriceUpdateStatus>('/site/admin/prices/update/pause')
  return response.data
}

export async function resumeAdminPriceUpdate() {
  const response = await apiClient.post<AdminPriceUpdateStatus>('/site/admin/prices/update/resume')
  return response.data
}

export async function cancelAdminPriceUpdate() {
  const response = await apiClient.post<AdminPriceUpdateStatus>('/site/admin/prices/update/cancel')
  return response.data
}

export type AdminUnparsedUrlsResponse = {
  total_urls_in_pkl: number
  parsed_ids: number
  unparsed_total: number
  missing_by_locale: Record<string, number>
  items: {
    url: string
    locale: string
    product_id: string
    product_name?: string | null
    added_at?: string | null
    regions_count: number
    ua_url: string
    exists_in_regions: string[]
    missing_regions: string[]
  }[]
  page: number
  limit: number
}

export type AdminUnparsedUrlCollectionStatus = {
  task_id?: string | null
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed'
  phase?: string | null
  message: string
  skipped?: boolean
  total_urls?: number
  processed_pages?: number
  total_pages?: number
  raw_urls?: number
  processed_concepts?: number
  total_concepts?: number
  expanded_urls?: number
  duplicates_removed?: number
  remaining?: number | null
  new_products_count?: number
  new_products?: string[]
  started_at?: string | null
  completed_at?: string | null
}

export async function fetchAdminUnparsedUrls(params: {
  page?: number
  limit?: number
  mode?: 'missing_all' | 'missing_any' | 'all'
  locale?: string
  search?: string
  region_count?: number
}) {
  const response = await apiClient.get<AdminUnparsedUrlsResponse>('/site/admin/unparsed-urls', { params })
  return response.data
}

export async function collectAdminUnparsedUrls() {
  const response = await apiClient.post<AdminUnparsedUrlCollectionStatus>(
    '/site/admin/unparsed-urls/collect',
    undefined,
    { timeout: 0 },
  )
  return response.data
}

export async function fetchAdminUnparsedUrlCollectionStatus() {
  const response = await apiClient.get<AdminUnparsedUrlCollectionStatus>(
    '/site/admin/unparsed-urls/collect/status',
  )
  return response.data
}

export async function fetchAdminProduct(productId: string, region: string) {
  const response = await apiClient.get<AdminProductDetails>(`/site/admin/products/${productId}`, {
    params: { region },
  })
  return response.data
}

export async function createAdminProduct(payload: AdminProductPayload) {
  const response = await apiClient.post<AdminProductDetails>('/site/admin/products', payload)
  return response.data
}

export async function manualParseAdminProduct(payload: AdminProductManualParsePayload) {
  const response = await apiClient.post<AdminProductManualParseStartResponse>(
    '/site/admin/products/manual-parse',
    payload,
    { timeout: 0 },
  )
  return response.data
}

export async function fetchManualParseAdminProductStatus(taskId: string) {
  const response = await apiClient.get<AdminProductManualParseStatusResponse>(
    `/site/admin/products/manual-parse/${taskId}`,
  )
  return response.data
}

export async function updateAdminProduct(productId: string, region: string, payload: AdminProductPayload) {
  const response = await apiClient.put<AdminProductDetails>(`/site/admin/products/${productId}`, payload, {
    params: { region },
  })
  return response.data
}

export async function deleteAdminProduct(productId: string, region: string) {
  const response = await apiClient.delete<{ message: string }>(`/site/admin/products/${productId}`, {
    params: { region },
  })
  return response.data
}

export async function deleteAdminProductGroup(productId: string) {
  const response = await apiClient.delete<{ message: string }>(`/site/admin/products/${productId}/all`)
  return response.data
}

export async function deleteAdminProductFavorite(productId: string, favoriteId: number) {
  const response = await apiClient.delete<{ message: string }>(`/site/admin/products/${productId}/favorites/${favoriteId}`)
  return response.data
}

export async function fetchAdminPurchases(params: {
  page?: number
  limit?: number
  status?: string
  search?: string
}) {
  const response = await apiClient.get<AdminPurchaseListResponse>('/site/admin/purchases', { params })
  return response.data
}

export async function fetchAdminPurchase(orderNumber: string) {
  const response = await apiClient.get<AdminPurchase>(`/site/admin/purchases/${orderNumber}`)
  return response.data
}

export async function updateAdminPurchase(orderNumber: string, payload: AdminPurchaseUpdatePayload) {
  const response = await apiClient.patch<AdminPurchase>(`/site/admin/purchases/${orderNumber}`, payload)
  return response.data
}

export async function fulfillAdminPurchase(orderNumber: string, payload: AdminPurchaseFulfillPayload) {
  const response = await apiClient.post<AdminPurchase>(`/site/admin/purchases/${orderNumber}/fulfill`, payload)
  return response.data
}

export async function deleteAdminPurchase(orderNumber: string) {
  const response = await apiClient.delete<{ message: string }>(`/site/admin/purchases/${orderNumber}`)
  return response.data
}
