export type AuthActionResponse = {
  message: string
  resend_available_in?: number | null
}

export type SiteUser = {
  id: string
  email?: string | null
  email_verified: boolean
  username?: string | null
  first_name?: string | null
  last_name?: string | null
  telegram_id?: number | null
  preferred_region: string
  show_ukraine_prices: boolean
  show_turkey_prices: boolean
  show_india_prices: boolean
  payment_email?: string | null
  platform?: string | null
  psn_email?: string | null
  role: 'admin' | 'client'
  is_admin: boolean
  is_active: boolean
  auth_providers: string[]
  created_at: string
  updated_at: string
  last_login_at?: string | null
}

export type SitePSNRegion = 'UA' | 'TR'

export type SitePSNAccount = {
  region: SitePSNRegion
  platform?: 'PS4' | 'PS5' | null
  psn_email?: string | null
  has_password: boolean
  has_backup_code: boolean
  updated_at?: string | null
}

export type SiteProfileResponse = {
  user: SiteUser
  psn_accounts: Record<SitePSNRegion, SitePSNAccount>
}

export type ProfilePreferencesPayload = {
  preferred_region: 'UA' | 'TR' | 'IN'
  payment_email?: string | null
}

export type ProfilePSNAccountPayload = {
  platform?: 'PS4' | 'PS5' | null
  psn_email?: string | null
  psn_password?: string | null
  backup_code?: string | null
}

export type AuthUserResponse = {
  user: SiteUser
}

export type RegisterPayload = {
  email: string
  password: string
  username?: string
  first_name?: string
  last_name?: string
  telegram_id?: number
  preferred_region?: string
  show_ukraine_prices?: boolean
  show_turkey_prices?: boolean
  show_india_prices?: boolean
  payment_email?: string
  platform?: string
  psn_email?: string
}

export type VerifyEmailPayload = {
  email: string
  code: string
}

export type ResendCodePayload = {
  email: string
}

export type LoginPayload = {
  email: string
  password: string
}

export type AuthProvidersResponse = {
  google_enabled: boolean
  vk_enabled: boolean
  telegram_enabled: boolean
  telegram_bot_username?: string | null
}

export type TelegramAuthPayload = {
  id: number
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}
