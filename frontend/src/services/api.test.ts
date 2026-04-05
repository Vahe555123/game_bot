import { describe, expect, it } from 'vitest'
import { buildApiUrl, resolveApiBaseUrl } from './api'

describe('resolveApiBaseUrl', () => {
  it('keeps a relative API path for proxy-based development', () => {
    expect(resolveApiBaseUrl('/api')).toBe('/api')
  })

  it('normalizes loopback hosts to the current frontend host', () => {
    expect(
      resolveApiBaseUrl('http://127.0.0.1:8000/api', {
        hostname: 'localhost',
      }),
    ).toBe('http://localhost:8000/api')
  })
})

describe('buildApiUrl', () => {
  it('builds an absolute OAuth URL when API base is absolute', () => {
    expect(buildApiUrl('/auth/oauth/google/start?next=%2Fprofile', 'http://localhost:8000/api')).toBe(
      'http://localhost:8000/api/auth/oauth/google/start?next=%2Fprofile',
    )
  })

  it('builds a proxy URL when API base is relative', () => {
    expect(buildApiUrl('/auth/me', '/api')).toBe('/api/auth/me')
  })
})
