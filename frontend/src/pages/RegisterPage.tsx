import { Navigate } from 'react-router-dom'
import { buildAuthModalPath } from '../components/auth/authModalState'

export function RegisterPage() {
  return <Navigate to={buildAuthModalPath({ pathname: '/', search: '', hash: '' }, 'register')} replace />
}
