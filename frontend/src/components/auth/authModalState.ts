export type AuthModalView = 'login' | 'register' | 'recover'

type LocationShape = {
  pathname: string
  search: string
  hash: string
}

export const AUTH_MODAL_QUERY_KEY = 'auth'
export const AUTH_MODAL_NEXT_QUERY_KEY = 'auth_next'
const AUTH_MODAL_FEEDBACK_QUERY_KEYS = ['auth_error', 'auth_provider']

function isSafePath(value: string | null | undefined): value is string {
  return Boolean(value && value.startsWith('/') && !value.startsWith('//'))
}

function buildSearch(searchParams: URLSearchParams) {
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

export function normalizeAuthModalView(value: string | null | undefined): AuthModalView | null {
  return value === 'login' || value === 'register' || value === 'recover' ? value : null
}

export function buildAuthModalPath(
  location: LocationShape,
  view: AuthModalView,
  nextPath?: string | null,
) {
  const searchParams = new URLSearchParams(location.search)

  searchParams.set(AUTH_MODAL_QUERY_KEY, view)

  if (isSafePath(nextPath)) {
    searchParams.set(AUTH_MODAL_NEXT_QUERY_KEY, nextPath)
  } else {
    searchParams.delete(AUTH_MODAL_NEXT_QUERY_KEY)
  }

  return `${location.pathname}${buildSearch(searchParams)}${location.hash}`
}

export function buildAuthModalReturnPath(location: LocationShape) {
  return `${location.pathname}${location.search}${location.hash}`
}

export function buildBaseAuthPath(location: LocationShape) {
  const searchParams = new URLSearchParams(location.search)

  searchParams.delete(AUTH_MODAL_QUERY_KEY)
  searchParams.delete(AUTH_MODAL_NEXT_QUERY_KEY)

  for (const key of AUTH_MODAL_FEEDBACK_QUERY_KEYS) {
    searchParams.delete(key)
  }

  return `${location.pathname}${buildSearch(searchParams)}${location.hash}`
}

export function resolveAuthSuccessPath(location: LocationShape, fallback = '/profile') {
  const searchParams = new URLSearchParams(location.search)
  const nextPath = searchParams.get(AUTH_MODAL_NEXT_QUERY_KEY)

  if (isSafePath(nextPath)) {
    return nextPath
  }

  const basePath = buildBaseAuthPath(location)
  return basePath === location.pathname ? fallback : basePath
}
