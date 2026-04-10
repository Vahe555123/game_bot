import type { SiteUser } from './auth'
import type { HelpContent, HelpContentPayload } from './help'
import type { PurchaseDelivery, PurchaseDeliveryItem } from './purchase'

export type AdminUser = SiteUser & {
  is_env_admin: boolean
  purchase_count: number
  total_spent_rub: number
}

export type AdminUserListResponse = {
  users: AdminUser[]
  total: number
  page: number
  limit: number
}

export type AdminUserPayload = {
  email?: string | null
  password?: string | null
  email_verified?: boolean
  username?: string | null
  first_name?: string | null
  last_name?: string | null
  telegram_id?: number | null
  preferred_region?: 'UA' | 'TR' | 'IN'
  payment_email?: string | null
  platform?: 'PS4' | 'PS5' | null
  psn_email?: string | null
  role?: 'admin' | 'client'
  is_active?: boolean
}

export type AdminProduct = {
  id: string
  region: 'UA' | 'TR' | 'IN'
  display_name: string
  favorites_count: number
  name?: string | null
  main_name?: string | null
  category?: string | null
  type?: string | null
  image?: string | null
  search_names?: string | null
  platforms?: string | null
  publisher?: string | null
  localization?: string | null
  rating?: number | null
  edition?: string | null
  price?: number | null
  old_price?: number | null
  ps_price?: number | null
  ea_price?: number | null
  price_uah?: number | null
  old_price_uah?: number | null
  price_try?: number | null
  old_price_try?: number | null
  price_inr?: number | null
  old_price_inr?: number | null
  ps_plus_price_uah?: number | null
  ps_plus_price_try?: number | null
  ps_plus_price_inr?: number | null
  plus_types?: string | null
  ps_plus: boolean
  ea_access?: string | null
  ps_plus_collection?: string | null
  discount?: number | null
  discount_end?: string | null
  tags?: string | null
  description?: string | null
  compound?: string | null
  info?: string | null
  players_min?: number | null
  players_max?: number | null
  players_online: boolean
  has_discount: boolean
  has_ps_plus: boolean
  has_ea_access: boolean
}

export type AdminProductFavorite = {
  id: number
  user_id: number
  telegram_id?: number | null
  username?: string | null
  first_name?: string | null
  last_name?: string | null
  full_name?: string | null
  preferred_region?: 'UA' | 'TR' | 'IN' | string | null
  payment_email?: string | null
  platform?: 'PS4' | 'PS5' | string | null
  psn_email?: string | null
  region?: string | null
  is_active: boolean
  favorited_at?: string | null
}

export type AdminProductDetails = AdminProduct & {
  regional_products: AdminProduct[]
  favorites: AdminProductFavorite[]
  available_regions: string[]
  missing_regions: string[]
  favorites_by_region: Record<string, number>
  regional_rows_total: number
  favorite_users_total: number
}

export type AdminProductListResponse = {
  products: AdminProduct[]
  total: number
  page: number
  limit: number
}

export type AdminProductSortMode = 'popular' | 'alphabet'

export type AdminProductPayload = {
  id?: string
  region?: 'UA' | 'TR' | 'IN'
  category?: string | null
  type?: string | null
  name?: string | null
  main_name?: string | null
  search_names?: string | null
  image?: string | null
  compound?: string | null
  platforms?: string | null
  publisher?: string | null
  localization?: string | null
  rating?: number | null
  info?: string | null
  edition?: string | null
  price?: number | null
  old_price?: number | null
  ps_price?: number | null
  ea_price?: number | null
  price_uah?: number | null
  old_price_uah?: number | null
  price_try?: number | null
  old_price_try?: number | null
  price_inr?: number | null
  old_price_inr?: number | null
  ps_plus_price_uah?: number | null
  ps_plus_price_try?: number | null
  ps_plus_price_inr?: number | null
  plus_types?: string | null
  ps_plus?: boolean
  ea_access?: string | null
  ps_plus_collection?: string | null
  discount?: number | null
  discount_end?: string | null
  tags?: string | null
  description?: string | null
  players_min?: number | null
  players_max?: number | null
  players_online?: boolean
}

export type AdminPurchase = {
  order_number: string
  status: 'payment_pending' | 'payment_review' | 'fulfilled' | 'cancelled'
  status_label: string
  site_user_id: string
  user_email?: string | null
  user_display_name?: string | null
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

export type AdminPurchaseListResponse = {
  orders: AdminPurchase[]
  total: number
  page: number
  limit: number
}

export type AdminPurchaseUpdatePayload = {
  status?: AdminPurchase['status']
  status_note?: string | null
  manager_contact_url?: string | null
  payment_url?: string | null
}

export type AdminPurchaseFulfillPayload = {
  delivery_title?: string | null
  delivery_message?: string | null
  delivery_items: PurchaseDeliveryItem[]
  status_note?: string | null
  send_email: boolean
}

export type AdminDashboard = {
  users: {
    total: number
    active: number
    verified: number
    admins: number
    clients: number
  }
  products: {
    total_rows: number
    unique_products: number
    discounted: number
    with_ps_plus: number
    regions: Record<string, number>
  }
  purchases: {
    total: number
    total_revenue_rub: number
    fulfilled_revenue_rub: number
    statuses: Record<string, number>
  }
  recent_users: AdminUser[]
  recent_orders: AdminPurchase[]
}

export type AdminHelpContent = HelpContent
export type AdminHelpContentPayload = HelpContentPayload
