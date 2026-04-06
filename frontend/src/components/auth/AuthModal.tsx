import { ExternalLink, LogIn, ShieldCheck, UserRoundPlus, X } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { login, register } from '../../services/auth'
import { getApiErrorMessage } from '../../utils/apiErrors'
import { TextField } from './FormField'
import { SocialAuthPanel } from './SocialAuthPanel'
import {
  buildAuthModalPath,
  buildAuthModalReturnPath,
  resolveAuthSuccessPath,
  type AuthModalView,
} from './authModalState'

type RegisterFormState = {
  email: string
  password: string
  confirmPassword: string
  paymentEmail: string
}

type AuthModalProps = {
  view: AuthModalView
  onClose: () => void
}

const DEFAULT_REGISTER_FORM: RegisterFormState = {
  email: '',
  password: '',
  confirmPassword: '',
  paymentEmail: '',
}

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-[16px] px-4 py-2.5 text-sm font-semibold transition ${
        active
          ? 'bg-brand-500 text-white shadow-glow'
          : 'bg-transparent text-slate-300 hover:bg-white/[0.05] hover:text-white'
      }`}
    >
      {children}
    </button>
  )
}

export function AuthModal({ view, onClose }: AuthModalProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { isAuthenticated, isAuthLoading, setAuthenticatedUser } = useAuth()

  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search])
  const oauthError = searchParams.get('auth_error')
  const oauthReturnPath = buildAuthModalReturnPath(location)
  const recoveryUrl = import.meta.env.VITE_MANAGER_TELEGRAM_URL || import.meta.env.VITE_TELEGRAM_BOT_URL || null

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [isLoginSubmitting, setIsLoginSubmitting] = useState(false)

  const [registerForm, setRegisterForm] = useState<RegisterFormState>(DEFAULT_REGISTER_FORM)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [isRegisterSubmitting, setIsRegisterSubmitting] = useState(false)

  useEffect(() => {
    if (typeof document === 'undefined') {
      return undefined
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleEscape)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleEscape)
    }
  }, [onClose])

  useEffect(() => {
    if (isAuthLoading || !isAuthenticated) {
      return
    }

    navigate(resolveAuthSuccessPath(location), { replace: true })
  }, [isAuthenticated, isAuthLoading, location, navigate])

  function switchView(nextView: AuthModalView) {
    navigate(buildAuthModalPath(location, nextView, searchParams.get('auth_next')), { replace: true })
  }

  function updateRegisterField<K extends keyof RegisterFormState>(field: K, value: RegisterFormState[K]) {
    setRegisterForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoginError(null)
    setIsLoginSubmitting(true)

    try {
      const response = await login({
        email: email.trim(),
        password,
      })

      setAuthenticatedUser(response.user)
      navigate(resolveAuthSuccessPath(location), { replace: true })
    } catch (requestError) {
      setLoginError(getApiErrorMessage(requestError, 'Не удалось войти в аккаунт.'))
    } finally {
      setIsLoginSubmitting(false)
    }
  }

  async function handleRegisterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setRegisterError(null)

    if (registerForm.password !== registerForm.confirmPassword) {
      setRegisterError('Пароли не совпадают.')
      return
    }

    setIsRegisterSubmitting(true)

    try {
      const response = await register({
        email: registerForm.email.trim(),
        password: registerForm.password,
        payment_email: registerForm.paymentEmail.trim() || undefined,
      })

      navigate(`/verify-email?email=${encodeURIComponent(registerForm.email.trim())}`, {
        replace: true,
        state: {
          message: response.message,
          resendAvailableIn: response.resend_available_in ?? null,
        },
      })
    } catch (requestError) {
      setRegisterError(getApiErrorMessage(requestError, 'Не удалось создать аккаунт.'))
    } finally {
      setIsRegisterSubmitting(false)
    }
  }

  const title = view === 'login' ? 'Войти в аккаунт' : 'Создать аккаунт'
  const description =
    view === 'login'
      ? 'Сохраните избранное, покупки и настройки профиля в одном месте.'
      : 'Регистрация занимает меньше минуты. Подтверждение придёт кодом на email.'

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-slate-950/78 px-3 py-3 backdrop-blur-md md:items-center md:px-4 md:py-6"
      onClick={onClose}
    >
      <div
        className="flex max-h-[calc(100dvh-1.5rem)] w-full max-w-[560px] flex-col overflow-hidden rounded-[30px] border border-white/10 bg-[#131922] shadow-card"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-5 py-5 md:px-6">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-brand-200/80">Аккаунт</p>
            <h2 className="mt-2 text-3xl text-white">{title}</h2>
            <p className="mt-3 max-w-md text-sm leading-7 text-slate-300">{description}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-slate-300 transition hover:border-white/20 hover:text-white"
            aria-label="Закрыть окно авторизации"
          >
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto px-5 pb-6 pt-5 md:px-6">
          <div className="grid grid-cols-2 gap-2 rounded-[20px] border border-white/10 bg-slate-950/50 p-1">
            <TabButton active={view === 'login'} onClick={() => switchView('login')}>
              Вход
            </TabButton>
            <TabButton active={view === 'register'} onClick={() => switchView('register')}>
              Регистрация
            </TabButton>
          </div>

          <div className="mt-5">
            <SocialAuthPanel nextPath={oauthReturnPath} compact />
          </div>

          {view === 'login' ? (
            <div className="mt-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-white">Вход по email</p>
                  <p className="mt-1 text-sm text-slate-400">Если пароль уже есть, используйте обычный вход.</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-100">
                  <LogIn size={18} />
                </div>
              </div>

              <form className="mt-5 space-y-4" onSubmit={handleLoginSubmit}>
                <TextField
                  label="Email адрес"
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
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

                {loginError || oauthError ? (
                  <div className="auth-alert auth-alert-error">{loginError ?? oauthError}</div>
                ) : null}

                <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                  <Link to="/verify-email" className="text-slate-300 transition hover:text-white">
                    У меня есть код подтверждения
                  </Link>
                  {recoveryUrl ? (
                    <a
                      href={recoveryUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 text-brand-200 transition hover:text-white"
                    >
                      <ExternalLink size={14} />
                      <span>Восстановить пароль / аккаунт</span>
                    </a>
                  ) : null}
                </div>

                <button
                  type="submit"
                  disabled={isLoginSubmitting}
                  className="btn-primary min-h-[50px] w-full disabled:opacity-60"
                >
                  <ShieldCheck size={16} />
                  {isLoginSubmitting ? 'Входим...' : 'Войти'}
                </button>
              </form>
            </div>
          ) : (
            <div className="mt-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-white">Регистрация по email</p>
                  <p className="mt-1 text-sm text-slate-400">Нужны только данные, которые реально пригодятся для входа и покупок.</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-100">
                  <UserRoundPlus size={18} />
                </div>
              </div>

              <form className="mt-5 space-y-4" onSubmit={handleRegisterSubmit}>
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
                  value={registerForm.email}
                  onChange={(event) => updateRegisterField('email', event.target.value)}
                  required
                />

                <div>
                  <TextField
                    label="Email для покупок"
                    type="email"
                    autoComplete="email"
                    placeholder="Можно указать тот же email"
                    value={registerForm.paymentEmail}
                    onChange={(event) => updateRegisterField('paymentEmail', event.target.value)}
                  />
                  <p className="mt-2 text-xs leading-6 text-slate-400">
                    К этому email будут привязаны все покупки.
                  </p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <TextField
                    label="Пароль"
                    type="password"
                    autoComplete="new-password"
                    hint="Минимум 8 символов"
                    placeholder="Создайте пароль"
                    value={registerForm.password}
                    onChange={(event) => updateRegisterField('password', event.target.value)}
                    required
                  />
                  <TextField
                    label="Повторите пароль"
                    type="password"
                    autoComplete="new-password"
                    placeholder="Повторите пароль"
                    value={registerForm.confirmPassword}
                    onChange={(event) => updateRegisterField('confirmPassword', event.target.value)}
                    required
                  />
                </div>

                {registerError || oauthError ? (
                  <div className="auth-alert auth-alert-error">{registerError ?? oauthError}</div>
                ) : null}

                <button
                  type="submit"
                  disabled={isRegisterSubmitting}
                  className="btn-primary min-h-[50px] w-full disabled:opacity-60"
                >
                  <ShieldCheck size={16} />
                  {isRegisterSubmitting ? 'Отправляем код...' : 'Зарегистрироваться'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
