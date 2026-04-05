import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getCurrentUser, logout as requestLogout } from '../services/auth'
import type { SiteUser } from '../types/auth'

type AuthContextValue = {
  user: SiteUser | null
  isAuthLoading: boolean
  isAuthenticated: boolean
  refreshUser: () => Promise<SiteUser | null>
  setAuthenticatedUser: (user: SiteUser | null) => void
  logoutUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SiteUser | null>(null)
  const [isAuthLoading, setIsAuthLoading] = useState(true)

  useEffect(() => {
    let ignore = false

    ;(async () => {
      try {
        const response = await getCurrentUser()
        if (!ignore) {
          startTransition(() => {
            setUser(response.user)
          })
        }
      } catch {
        if (!ignore) {
          startTransition(() => {
            setUser(null)
          })
        }
      } finally {
        if (!ignore) {
          setIsAuthLoading(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [])

  async function refreshUser() {
    try {
      const response = await getCurrentUser()
      startTransition(() => {
        setUser(response.user)
      })
      return response.user
    } catch {
      startTransition(() => {
        setUser(null)
      })
      return null
    } finally {
      setIsAuthLoading(false)
    }
  }

  function setAuthenticatedUser(nextUser: SiteUser | null) {
    startTransition(() => {
      setUser(nextUser)
    })
    setIsAuthLoading(false)
  }

  async function logoutUser() {
    try {
      await requestLogout()
    } finally {
      startTransition(() => {
        setUser(null)
      })
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthLoading,
        isAuthenticated: Boolean(user),
        refreshUser,
        setAuthenticatedUser,
        logoutUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }

  return context
}
