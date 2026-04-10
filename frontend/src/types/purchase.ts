export type PurchaseDeliveryItem = {
  label: string
  value: string
}

export type PurchaseDelivery = {
  title?: string | null
  message?: string | null
  items: PurchaseDeliveryItem[]
}

export type PurchaseOrder = {
  order_number: string
  status: string
  status_label: string
  product_id: string
  product_name: string
  product_region: string
  product_image?: string | null
  product_platforms?: string | null
  currency_code: string
  local_price: number
  price_rub: number
  use_ps_plus: boolean
  payment_email?: string | null
  psn_email?: string | null
  platform?: string | null
  payment_provider: string
  payment_type: string
  payment_url?: string | null
  payment_metadata: Record<string, unknown>
  manager_contact_url?: string | null
  status_note?: string | null
  delivery?: PurchaseDelivery | null
  created_at: string
  updated_at: string
  payment_submitted_at?: string | null
  fulfilled_at?: string | null
}

export type PurchaseListResponse = {
  orders: PurchaseOrder[]
}

export type CreatePurchaseCheckoutPayload = {
  product_id: string
  region: string
  use_ps_plus?: boolean
  purchase_email?: string
  psn_email?: string
  psn_password?: string
  backup_code?: string
}
