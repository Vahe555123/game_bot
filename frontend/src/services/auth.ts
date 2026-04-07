import type {
  AuthActionResponse,
  AuthProvidersResponse,
  ProfilePreferencesPayload,
  ProfilePSNAccountPayload,
  AuthUserResponse,
  LoginPayload,
  PasswordResetConfirmPayload,
  RegisterPayload,
  ResendCodePayload,
  SiteProfileResponse,
  TelegramAuthPayload,
  VerifyEmailPayload,
} from '../types/auth'
import { apiClient, buildApiUrl } from './api'

export async function register(payload: RegisterPayload) {
  const response = await apiClient.post<AuthActionResponse>('/auth/register', payload)
  return response.data
}

export async function resendCode(payload: ResendCodePayload) {
  const response = await apiClient.post<AuthActionResponse>('/auth/resend-code', payload)
  return response.data
}

export async function verifyEmail(payload: VerifyEmailPayload) {
  const response = await apiClient.post<AuthUserResponse>('/auth/verify-email', payload)
  return response.data
}

export async function requestPasswordReset(payload: ResendCodePayload) {
  const response = await apiClient.post<AuthActionResponse>('/auth/password-reset/request', payload)
  return response.data
}

export async function resendPasswordReset(payload: ResendCodePayload) {
  const response = await apiClient.post<AuthActionResponse>('/auth/password-reset/resend', payload)
  return response.data
}

export async function confirmPasswordReset(payload: PasswordResetConfirmPayload) {
  const response = await apiClient.post<AuthUserResponse>('/auth/password-reset/confirm', payload)
  return response.data
}

export async function login(payload: LoginPayload) {
  const response = await apiClient.post<AuthUserResponse>('/auth/login', payload)
  return response.data
}

export async function logout() {
  const response = await apiClient.post<AuthActionResponse>('/auth/logout')
  return response.data
}

export async function getCurrentUser() {
  const response = await apiClient.get<AuthUserResponse>('/auth/me')
  return response.data
}

export async function getProfile() {
  const response = await apiClient.get<SiteProfileResponse>('/auth/profile')
  return response.data
}

export async function updateProfilePreferences(payload: ProfilePreferencesPayload) {
  const response = await apiClient.put<SiteProfileResponse>('/auth/profile/preferences', payload)
  return response.data
}

export async function updateProfilePsnAccount(region: 'UA' | 'TR', payload: ProfilePSNAccountPayload) {
  const response = await apiClient.put<SiteProfileResponse>(`/auth/profile/psn/${region}`, payload)
  return response.data
}

export async function getAuthProviders() {
  const response = await apiClient.get<AuthProvidersResponse>('/auth/providers')
  return response.data
}

export async function telegramLogin(payload: TelegramAuthPayload) {
  const response = await apiClient.post<AuthUserResponse>('/auth/oauth/telegram', payload)
  return response.data
}

export function getOAuthStartUrl(provider: 'google' | 'vk', nextPath = '/profile') {
  const params = new URLSearchParams({ next: nextPath })
  return buildApiUrl(`/auth/oauth/${provider}/start?${params.toString()}`)
}
