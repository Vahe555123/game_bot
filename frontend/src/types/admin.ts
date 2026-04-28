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

export type AdminProductSortMode = 'popular' | 'alphabet' | 'added_desc' | 'release_desc'

export type AdminDiscountUpdateLogEntry = {
  time: string
  message: string
}

export type AdminFavoriteDiscountNotificationSummary = {
  candidates: number
  sent: number
  email_sent: number
  telegram_sent: number
  skipped_existing: number
  no_recipient: number
  failed: number
}

export type AdminFavoriteDiscountNotificationResponse = {
  message: string
  discounted_products: number
  force_resend: boolean
  summary: AdminFavoriteDiscountNotificationSummary
}

export type AdminDiscountUpdateStatus = {
  task_id?: string | null
  status: 'idle' | 'pending' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed'
  phase?: string | null
  message: string
  mode?: 'test' | 'full' | string | null
  total?: number | null
  processed?: number | null
  saved?: number | null
  failed?: number | null
  remaining?: number | null
  percent?: number | null
  discount_records?: number | null
  notification_summary?: Record<string, number> | null
  logs?: AdminDiscountUpdateLogEntry[]
  started_at?: string | null
  completed_at?: string | null
  result?: Record<string, unknown> | null
  control_state?: 'idle' | 'running' | 'paused' | 'cancel_requested' | 'cancelled' | 'completed' | 'failed' | string | null
}

// Обновление цен — структурно совместимо с discount-update,
// без discount-специфичных полей (discount_records, notification_summary).
export type AdminPriceUpdateStatus = {
  task_id?: string | null
  status: 'idle' | 'pending' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed'
  phase?: string | null
  message: string
  mode?: 'test' | 'full' | string | null
  total?: number | null
  processed?: number | null
  saved?: number | null
  failed?: number | null
  remaining?: number | null
  percent?: number | null
  logs?: AdminDiscountUpdateLogEntry[]
  started_at?: string | null
  completed_at?: string | null
  result?: Record<string, unknown> | null
  control_state?: 'idle' | 'running' | 'paused' | 'cancel_requested' | 'cancelled' | 'completed' | 'failed' | string | null
}

// Прокси-пул для парсера: статус каждого прокси и активный.
export type AdminProxyEntry = {
  label: string                 // host:port (без логин:пароль)
  status: 'ok' | 'cooldown' | 'banned' | 'unknown' | 'failed_check' | string
  fail_count: number
  success_count: number
  last_check_at: number         // epoch seconds; 0 если ещё не проверяли
  last_used_at: number
  last_error: string | null
  cooldown_seconds_left: number
  is_active: boolean
}

export type AdminProxyStatus = {
  enabled: boolean
  size: number
  active_label: string | null
  active_status: string | null
  ban_threshold: number
  cooldown_seconds: number
  proxies: AdminProxyEntry[]
}

// Полный парсинг (mode 1) — расширенный набор метрик:
//   empty_returns — товары которые parse() вернул пустыми (ничего не сохранилось)
//   ban_count_403 — сколько 403/Akamai-banned ответов получили
//   missing_ua/tr/in — в скольких товарах не получилось спарсить регион
//   consecutive_bans — текущая длина серии 403'ок (для индикации "прокси умер")
export type AdminFullParseStatus = {
  task_id?: string | null
  status: 'idle' | 'pending' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed'
  phase?: string | null
  message: string
  mode?: 'test' | 'full' | string | null
  total?: number | null
  processed?: number | null
  saved?: number | null
  failed?: number | null
  empty_returns?: number | null
  ban_count_403?: number | null
  missing_ua?: number | null
  missing_tr?: number | null
  missing_in?: number | null
  avg_per_product_seconds?: number | null
  consecutive_bans?: number | null
  remaining?: number | null
  percent?: number | null
  logs?: AdminDiscountUpdateLogEntry[]
  started_at?: string | null
  completed_at?: string | null
  result?: Record<string, unknown> | null
  control_state?: 'idle' | 'running' | 'paused' | 'cancel_requested' | 'cancelled' | 'completed' | 'failed' | string | null
  orphans?: AdminFullParseOrphanTask[]
}

export type AdminFullParseOrphanTask = {
  task_id: string
  mode?: 'test' | 'full' | string | null
  status?: string | null
  total?: number | null
  processed?: number | null
  saved_total?: number | null
  failed_total?: number | null
  products_path?: string | null
  updated_at?: string | null
}

export type AdminProductManualParsePayload = {
  ua_url?: string | null
  tr_url?: string | null
  in_url?: string | null
  save_to_db?: boolean
}

export type AdminProductManualParseRecord = {
  id?: string | null
  region?: string | null
  name?: string | null
  main_name?: string | null
  edition?: string | null
  price_rub?: number | null
  price_rub_region?: string | null
  localization?: string | null
}

export type AdminProductManualParseResponse = {
  message: string
  parsed_total: number
  final_total: number
  updated_count: number
  added_count: number
  duplicates_removed: number
  result_count: number
  db_updated: boolean
  errors: string[]
  records: AdminProductManualParseRecord[]
}

export type AdminProductManualParseStartResponse = {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  message: string
}

export type AdminProductManualParseStatusResponse = {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  message: string
  result?: AdminProductManualParseResponse | null
}

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
