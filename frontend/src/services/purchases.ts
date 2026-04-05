import { apiClient } from './api'
import type { CreatePurchaseCheckoutPayload, PurchaseListResponse, PurchaseOrder } from '../types/purchase'

export async function createPurchaseCheckout(payload: CreatePurchaseCheckoutPayload) {
  const response = await apiClient.post<PurchaseOrder>('/site/purchases/checkout', payload)
  return response.data
}

export async function listPurchases(days?: number) {
  const response = await apiClient.get<PurchaseListResponse>('/site/purchases', {
    params: days ? { days } : undefined,
  })
  return response.data
}
