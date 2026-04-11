import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { addSiteFavorite, listSiteFavorites, removeSiteFavorite } from '../services/favorites'
import { useAuth } from './AuthContext'
import type { FavoriteEntry, FavoriteTogglePayload } from './favoritesStorage'
import { addFavoriteEntry, mergeFavoriteCollections, parseFavorites, removeFavoriteEntry, toggleFavoriteEntry } from './favoritesStorage'

type FavoritesContextValue = {
  favorites: FavoriteEntry[]
  isFavoritesLoading: boolean
  isFavorite: (productId: string) => boolean
  toggleFavorite: (payload: FavoriteTogglePayload) => void
}

const STORAGE_PREFIX = 'site_favorites'
const GUEST_STORAGE_KEY = `${STORAGE_PREFIX}:guest`
const FavoritesContext = createContext<FavoritesContextValue | null>(null)

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const { user, isAuthLoading } = useAuth()
  const storageKey = `${STORAGE_PREFIX}:${user?.id ?? 'guest'}`

  const [favorites, setFavorites] = useState<FavoriteEntry[]>([])
  const [isFavoritesLoading, setIsFavoritesLoading] = useState(true)
  const [loadedKey, setLoadedKey] = useState<string | null>(null)

  useEffect(() => {
    if (isAuthLoading || typeof window === 'undefined') {
      return
    }

    let ignore = false
    const localStorageKeys = user?.id ? Array.from(new Set([storageKey, GUEST_STORAGE_KEY])) : [storageKey]
    setIsFavoritesLoading(true)

    ;(async () => {
      const localFavorites = mergeFavoriteCollections(
        localStorageKeys.map((key) => parseFavorites(window.localStorage.getItem(key))),
      )

      let nextFavorites = localFavorites

      if (user) {
        try {
          let remoteFavorites = await listSiteFavorites()
          const remoteIds = new Set(remoteFavorites.map((entry) => entry.productId))
          const missingRemoteFavorites = localFavorites.filter((entry) => !remoteIds.has(entry.productId))

          if (missingRemoteFavorites.length) {
            await Promise.allSettled(
              missingRemoteFavorites.map((entry) =>
                addSiteFavorite({
                  productId: entry.productId,
                  region: entry.region,
                }),
              ),
            )
            remoteFavorites = mergeFavoriteCollections([remoteFavorites, missingRemoteFavorites])
          }

          nextFavorites = mergeFavoriteCollections([remoteFavorites, localFavorites])
        } catch {
          nextFavorites = localFavorites
        }
      }

      if (ignore) {
        return
      }

      setFavorites(nextFavorites)
      setLoadedKey(storageKey)
      setIsFavoritesLoading(false)

      if (storageKey !== GUEST_STORAGE_KEY && localStorageKeys.includes(GUEST_STORAGE_KEY)) {
        window.localStorage.removeItem(GUEST_STORAGE_KEY)
      }
    })()

    return () => {
      ignore = true
    }
  }, [isAuthLoading, storageKey, user])

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
    const favoriteAlreadyExists = isFavorite(payload.productId)
    setFavorites((current) => toggleFavoriteEntry(current, payload))

    if (!user) {
      return
    }

    void (async () => {
      try {
        if (favoriteAlreadyExists) {
          await removeSiteFavorite(payload.productId)
          return
        }

        const savedFavorite = await addSiteFavorite(payload)
        setFavorites((current) => mergeFavoriteCollections([current, [savedFavorite]]))
      } catch {
        setFavorites((current) =>
          favoriteAlreadyExists ? addFavoriteEntry(current, payload) : removeFavoriteEntry(current, payload.productId),
        )
      }
    })()
  }

  return (
    <FavoritesContext.Provider
      value={{
        favorites,
        isFavoritesLoading,
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
