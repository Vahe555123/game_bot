import { Navigate, useLocation } from 'react-router-dom'
import { buildAuthModalPath } from '../components/auth/authModalState'

export function LoginPage() {
  const location = useLocation()
  const nextPath = new URLSearchParams(location.search).get('next')

  return <Navigate to={buildAuthModalPath({ pathname: '/', search: '', hash: '' }, 'login', nextPath)} replace />
}
