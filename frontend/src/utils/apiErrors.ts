import axios from 'axios'

type ApiErrorDetail = {
  message?: string
  [key: string]: unknown
}

export function getApiErrorDetail(error: unknown): string | ApiErrorDetail | null {
  if (!axios.isAxiosError(error)) {
    return null
  }

  const detail = error.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }

  if (detail && typeof detail === 'object') {
    return detail as ApiErrorDetail
  }

  return null
}

export function getApiErrorMessage(error: unknown, fallback = 'Не удалось выполнить запрос.') {
  const detail = getApiErrorDetail(error)

  if (typeof detail === 'string') {
    return detail
  }

  if (detail && typeof detail.message === 'string') {
    return detail.message
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

export function getApiErrorNumber(error: unknown, key: string) {
  const detail = getApiErrorDetail(error)
  if (!detail || typeof detail === 'string') {
    return null
  }

  const value = detail[key]
  return typeof value === 'number' ? value : null
}
