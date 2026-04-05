import type {
  AdminDashboard,
  AdminProduct,
  AdminProductListResponse,
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
}) {
  const response = await apiClient.get<AdminProductListResponse>('/site/admin/products', { params })
  return response.data
}

export async function fetchAdminProduct(productId: string, region: string) {
  const response = await apiClient.get<AdminProduct>(`/site/admin/products/${productId}`, {
    params: { region },
  })
  return response.data
}

export async function createAdminProduct(payload: AdminProductPayload) {
  const response = await apiClient.post<AdminProduct>('/site/admin/products', payload)
  return response.data
}

export async function updateAdminProduct(productId: string, region: string, payload: AdminProductPayload) {
  const response = await apiClient.put<AdminProduct>(`/site/admin/products/${productId}`, payload, {
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
