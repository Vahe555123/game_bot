import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { GuestOnly, RequireAdmin, RequireAuth } from './components/auth/RouteGuards'
import { SiteLayout } from './components/layout/SiteLayout'
import { AuthProvider } from './context/AuthContext'
import { FavoritesProvider } from './context/FavoritesContext'
import { AdminPage } from './pages/AdminPage'
import { CatalogPage } from './pages/CatalogPage'
import { FavoritesPage } from './pages/FavoritesPage'
import { HelpPage } from './pages/HelpPage'
import { LoginPage } from './pages/LoginPage'
import { ProductPage } from './pages/ProductPage'
import { ProfilePage } from './pages/ProfilePage'
import { RegisterPage } from './pages/RegisterPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'

function App() {
  return (
    <AuthProvider>
      <FavoritesProvider>
        <BrowserRouter>
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
      </FavoritesProvider>
    </AuthProvider>
  )
}

export default App
