import axios from 'axios'

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1'])
const ABSOLUTE_URL_PATTERN = /^https?:\/\//i

function trimTrailingSlash(value: string) {
  return value.replace(/\/$/, '')
}

export function resolveApiBaseUrl(
  rawBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api',
  browserLocation: Pick<Location, 'hostname'> | undefined = typeof window !== 'undefined' ? window.location : undefined,
) {
  const normalizedBaseUrl = trimTrailingSlash(rawBaseUrl || '/api')

  if (!browserLocation || !ABSOLUTE_URL_PATTERN.test(normalizedBaseUrl)) {
    return normalizedBaseUrl || '/api'
  }

  const apiUrl = new URL(normalizedBaseUrl)

  if (
    LOOPBACK_HOSTS.has(browserLocation.hostname) &&
    LOOPBACK_HOSTS.has(apiUrl.hostname) &&
    apiUrl.hostname !== browserLocation.hostname
  ) {
    apiUrl.hostname = browserLocation.hostname
  }

  return trimTrailingSlash(apiUrl.toString())
}

export function buildApiUrl(path: string, baseUrl = resolveApiBaseUrl()) {
  const normalizedPath = path.replace(/^\/+/, '')

  if (ABSOLUTE_URL_PATTERN.test(baseUrl)) {
    return new URL(normalizedPath, `${baseUrl}/`).toString()
  }

  return `${trimTrailingSlash(baseUrl)}/${normalizedPath}`
}

const baseURL = resolveApiBaseUrl()

export const apiClient = axios.create({
  baseURL,
  timeout: 15000,
  withCredentials: true,
})
