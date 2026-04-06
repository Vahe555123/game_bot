import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { buildAuthModalPath } from './authModalState'

function AuthLoadingState() {
  return (
    <div className="container py-12">
      <div className="panel-soft rounded-[28px] px-6 py-16 text-center">
        <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-brand-300/30 border-t-brand-300" />
        <p className="mt-5 text-sm text-slate-300">Проверяем текущую сессию...</p>
      </div>
    </div>
  )
}

export function RequireAuth() {
  const { isAuthenticated, isAuthLoading } = useAuth()
  const location = useLocation()

  if (isAuthLoading) {
    return <AuthLoadingState />
  }

  if (!isAuthenticated) {
    const redirectTarget = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to={buildAuthModalPath({ pathname: '/', search: '', hash: '' }, 'login', redirectTarget)} replace />
  }

  return <Outlet />
}

export function GuestOnly() {
  const { isAuthenticated, isAuthLoading } = useAuth()

  if (isAuthLoading) {
    return <AuthLoadingState />
  }

  if (isAuthenticated) {
    return <Navigate to="/profile" replace />
  }

  return <Outlet />
}

export function RequireAdmin() {
  const { isAuthenticated, isAuthLoading, user } = useAuth()

  if (isAuthLoading) {
    return <AuthLoadingState />
  }

  if (!isAuthenticated) {
    return <Navigate to={buildAuthModalPath({ pathname: '/', search: '', hash: '' }, 'login', '/admin')} replace />
  }

  if (!user?.is_admin) {
    return <Navigate to="/profile" replace />
  }

  return <Outlet />
}
