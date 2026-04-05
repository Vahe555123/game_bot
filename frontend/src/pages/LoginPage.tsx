import { LogIn, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthShell } from '../components/auth/AuthShell'
import { TextField } from '../components/auth/FormField'
import { SocialAuthPanel } from '../components/auth/SocialAuthPanel'
import { useAuth } from '../context/AuthContext'
import { login } from '../services/auth'
import { getApiErrorMessage } from '../utils/apiErrors'

function getSafeNext(searchParams: URLSearchParams) {
  const next = searchParams.get('next')
  return next && next.startsWith('/') ? next : '/profile'
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setAuthenticatedUser } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const nextPath = getSafeNext(searchParams)

  useEffect(() => {
    const socialError = searchParams.get('auth_error')
    if (socialError) {
      setError(socialError)
    }
  }, [searchParams])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const response = await login({
        email: email.trim(),
        password,
      })

      setAuthenticatedUser(response.user)
      navigate(nextPath, { replace: true })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Не удалось войти в аккаунт.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Авторизация"
      title="Вход в аккаунт сайта"
      description="Используй email и пароль, чтобы открыть личный профиль, покупки и настройки, знакомые по miniapp."
      asideTitle="Быстрый вход"
      asideText="После входа профиль сайта будет работать через cookie-сессию, без передачи данных пользователя в URL."
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-brand-200/80">Логин</p>
          <h2 className="mt-3 text-3xl text-white">Добро пожаловать обратно</h2>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-100">
          <LogIn size={20} />
        </div>
      </div>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <TextField
          label="Пароль"
          type="password"
          autoComplete="current-password"
          placeholder="Введите пароль"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error ? <div className="auth-alert auth-alert-error">{error}</div> : null}

        <div className="flex flex-col gap-3 sm:flex-row">
          <button type="submit" disabled={isSubmitting} className="btn-primary flex-1 disabled:opacity-60">
            <ShieldCheck size={16} />
            {isSubmitting ? 'Входим...' : 'Войти'}
          </button>
          <Link to="/verify-email" className="btn-secondary flex-1 text-center">
            Ввести код
          </Link>
        </div>
      </form>

      <div className="mt-6">
        <SocialAuthPanel nextPath={nextPath} />
      </div>

      <div className="mt-6 rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
        <p className="text-sm text-slate-300">
          Ещё нет аккаунта?{' '}
          <Link to="/register" className="font-semibold text-brand-200 transition hover:text-white">
            Создать профиль
          </Link>
        </p>
      </div>
    </AuthShell>
  )
}
