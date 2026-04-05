import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useAuth } from './AuthContext'
import type { FavoriteEntry, FavoriteTogglePayload } from './favoritesStorage'
import { parseFavorites, toggleFavoriteEntry } from './favoritesStorage'

type FavoritesContextValue = {
  favorites: FavoriteEntry[]
  isFavorite: (productId: string) => boolean
  toggleFavorite: (payload: FavoriteTogglePayload) => void
}

const STORAGE_PREFIX = 'site_favorites'
const FavoritesContext = createContext<FavoritesContextValue | null>(null)

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const { user, isAuthLoading } = useAuth()
  const storageKey = `${STORAGE_PREFIX}:${user?.id ?? 'guest'}`

  const [favorites, setFavorites] = useState<FavoriteEntry[]>([])
  const [loadedKey, setLoadedKey] = useState<string | null>(null)

  useEffect(() => {
    if (isAuthLoading) {
      return
    }

    const rawValue = window.localStorage.getItem(storageKey)
    const storedFavorites = parseFavorites(rawValue)
    setFavorites(storedFavorites)
    setLoadedKey(storageKey)
  }, [isAuthLoading, storageKey])

  useEffect(() => {
    if (!loadedKey || loadedKey !== storageKey || typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(storageKey, JSON.stringify(favorites))
  }, [favorites, loadedKey, storageKey])

  function isFavorite(productId: string) {
    return favorites.some((entry) => entry.productId === productId)
  }

  function toggleFavorite(payload: FavoriteTogglePayload) {
    setFavorites((current) => toggleFavoriteEntry(current, payload))
  }

  return (
    <FavoritesContext.Provider
      value={{
        favorites,
        isFavorite,
        toggleFavorite,
      }}
    >
      {children}
    </FavoritesContext.Provider>
  )
}

export function useFavorites() {
  const context = useContext(FavoritesContext)

  if (!context) {
    throw new Error('useFavorites must be used inside FavoritesProvider')
  }

  return context
}
