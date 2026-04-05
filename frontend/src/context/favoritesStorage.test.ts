import { describe, expect, it } from 'vitest'
import { parseFavorites, toggleFavoriteEntry, type FavoriteEntry } from './favoritesStorage'

describe('parseFavorites', () => {
  it('migrates legacy string arrays', () => {
    const favorites = parseFavorites(JSON.stringify(['game-1', 'game-2']))

    expect(favorites).toHaveLength(2)
    expect(favorites[0]).toMatchObject({ productId: 'game-1', region: null })
    expect(favorites[1]).toMatchObject({ productId: 'game-2', region: null })
  })

  it('keeps structured entries and removes duplicates', () => {
    const favorites = parseFavorites(
      JSON.stringify([
        { productId: 'game-1', region: 'tr', addedAt: '2026-04-04T18:00:00.000Z' },
        { productId: 'game-1', region: 'ua', addedAt: '2026-04-04T18:10:00.000Z' },
        { productId: 'game-2', region: 'IN', addedAt: '2026-04-04T19:00:00.000Z' },
      ]),
    )

    expect(favorites).toEqual([
      { productId: 'game-1', region: 'TR', addedAt: '2026-04-04T18:00:00.000Z' },
      { productId: 'game-2', region: 'IN', addedAt: '2026-04-04T19:00:00.000Z' },
    ])
  })
})

describe('toggleFavoriteEntry', () => {
  it('adds new entries with normalized region', () => {
    const favorites = toggleFavoriteEntry([], {
      productId: 'game-1',
      region: 'tr',
    })

    expect(favorites).toHaveLength(1)
    expect(favorites[0]).toMatchObject({ productId: 'game-1', region: 'TR' })
  })

  it('removes existing entries by product id', () => {
    const current: FavoriteEntry[] = [
      { productId: 'game-1', region: 'TR', addedAt: '2026-04-04T18:00:00.000Z' },
      { productId: 'game-2', region: 'UA', addedAt: '2026-04-04T19:00:00.000Z' },
    ]

    expect(toggleFavoriteEntry(current, { productId: 'game-1' })).toEqual([
      { productId: 'game-2', region: 'UA', addedAt: '2026-04-04T19:00:00.000Z' },
    ])
  })
})
