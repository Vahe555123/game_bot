import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { GuestOnly, RequireAdmin, RequireAuth } from './components/auth/RouteGuards'
import { SiteLayout } from './components/layout/SiteLayout'
import { AuthProvider } from './context/AuthContext'
import { FavoritesProvider } from './context/FavoritesContext'
import { HelpContentProvider } from './context/HelpContentContext'
import { AdminPage } from './pages/AdminPage'
import { CatalogPage } from './pages/CatalogPage'
import { FavoritesPage } from './pages/FavoritesPage'
import { HelpPage } from './pages/HelpPage'
import { LoginPage } from './pages/LoginPage'
import { ProductPage } from './pages/ProductPage'
import { ProfilePage } from './pages/ProfilePage'
import { RegisterPage } from './pages/RegisterPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'

const MOBILE_VIEWPORT_CONTENT = 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover'

function ViewportManager() {
  const location = useLocation()

  useEffect(() => {
    if (typeof document === 'undefined') {
      return
    }

    const viewportMeta = document.querySelector('meta[name="viewport"]')
    if (viewportMeta) {
      viewportMeta.setAttribute('content', MOBILE_VIEWPORT_CONTENT)
    }
  }, [location.pathname, location.search, location.hash])

  return null
}

function App() {
  return (
    <AuthProvider>
      <FavoritesProvider>
        <HelpContentProvider>
          <BrowserRouter>
            <ViewportManager />
            <Routes>
              <Route element={<SiteLayout />}>
                <Route index element={<CatalogPage />} />
                <Route path="/catalog" element={<CatalogPage />} />
                <Route path="/catalog/:productId" element={<ProductPage />} />
                <Route path="/favorites" element={<FavoritesPage />} />
                <Route path="/help" element={<HelpPage />} />

                <Route element={<GuestOnly />}>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route path="/verify-email" element={<VerifyEmailPage />} />
                </Route>

                <Route element={<RequireAuth />}>
                  <Route path="/profile" element={<ProfilePage />} />
                </Route>

                <Route element={<RequireAdmin />}>
                  <Route path="/admin" element={<AdminPage />} />
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </HelpContentProvider>
      </FavoritesProvider>
    </AuthProvider>
  )
}

export default App
