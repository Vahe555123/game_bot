import { ArrowLeft, KeyRound, LogIn, RotateCcw, ShieldCheck, UserRoundPlus, X } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import {
  confirmPasswordReset,
  login,
  register,
  requestPasswordReset,
  resendPasswordReset,
} from '../../services/auth'
import { getApiErrorMessage, getApiErrorNumber } from '../../utils/apiErrors'
import { TextField } from './FormField'
import { SocialAuthPanel } from './SocialAuthPanel'
import {
  buildAuthModalPath,
  resolveAuthSuccessPath,
  type AuthModalView,
} from './authModalState'

type RegisterFormState = {
  email: string
  password: string
  confirmPassword: string
  paymentEmail: string
}

type RecoverFormState = {
  email: string
  code: string
  newPassword: string
  confirmPassword: string
}

type RecoverStep = 'request' | 'confirm'

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

const DEFAULT_RECOVER_FORM: RecoverFormState = {
  email: '',
  code: '',
  newPassword: '',
  confirmPassword: '',
}

function formatCooldown(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  return `${minutes}:${String(remain).padStart(2, '0')}`
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
  const oauthReturnPath = resolveAuthSuccessPath(location)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const [isLoginSubmitting, setIsLoginSubmitting] = useState(false)

  const [registerForm, setRegisterForm] = useState<RegisterFormState>(DEFAULT_REGISTER_FORM)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [isRegisterSubmitting, setIsRegisterSubmitting] = useState(false)

  const [recoverForm, setRecoverForm] = useState<RecoverFormState>(DEFAULT_RECOVER_FORM)
  const [recoverStep, setRecoverStep] = useState<RecoverStep>('request')
  const [recoverError, setRecoverError] = useState<string | null>(null)
  const [recoverInfo, setRecoverInfo] = useState<string | null>(null)
  const [recoverCooldown, setRecoverCooldown] = useState(0)
  const [isRecoverRequestSubmitting, setIsRecoverRequestSubmitting] = useState(false)
  const [isRecoverConfirmSubmitting, setIsRecoverConfirmSubmitting] = useState(false)
  const [isRecoverResending, setIsRecoverResending] = useState(false)

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

  useEffect(() => {
    if (recoverCooldown <= 0) {
      return undefined
    }

    const timerId = window.setInterval(() => {
      setRecoverCooldown((current) => (current <= 1 ? 0 : current - 1))
    }, 1000)

    return () => {
      window.clearInterval(timerId)
    }
  }, [recoverCooldown])

  function switchView(nextView: AuthModalView) {
    navigate(buildAuthModalPath(location, nextView, searchParams.get('auth_next')), { replace: true })
  }

  function updateRegisterField<K extends keyof RegisterFormState>(field: K, value: RegisterFormState[K]) {
    setRegisterForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function updateRecoverField<K extends keyof RecoverFormState>(field: K, value: RecoverFormState[K]) {
    setRecoverForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function openRecoveryView() {
    setRecoverForm((current) => ({
      ...current,
      email: current.email || email.trim(),
    }))
    setRecoverError(null)
    setRecoverInfo(null)
    switchView('recover')
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

  async function handleRecoverRequestSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setRecoverError(null)
    setRecoverInfo(null)
    setIsRecoverRequestSubmitting(true)

    try {
      const normalizedEmail = recoverForm.email.trim()
      const response = await requestPasswordReset({ email: normalizedEmail })
      setRecoverForm((current) => ({
        ...current,
        email: normalizedEmail,
        code: '',
        newPassword: '',
        confirmPassword: '',
      }))
      setRecoverStep('confirm')
      setRecoverInfo(response.message)
      setRecoverCooldown(response.resend_available_in ?? 0)
    } catch (requestError) {
      setRecoverError(getApiErrorMessage(requestError, 'Не удалось отправить код для восстановления пароля.'))
      const resendAvailableIn = getApiErrorNumber(requestError, 'resend_available_in')
      if (resendAvailableIn) {
        setRecoverStep('confirm')
        setRecoverCooldown(resendAvailableIn)
      }
    } finally {
      setIsRecoverRequestSubmitting(false)
    }
  }

  async function handleRecoverConfirmSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setRecoverError(null)
    setRecoverInfo(null)

    if (recoverForm.newPassword !== recoverForm.confirmPassword) {
      setRecoverError('Пароли не совпадают.')
      return
    }

    setIsRecoverConfirmSubmitting(true)

    try {
      const response = await confirmPasswordReset({
        email: recoverForm.email.trim(),
        code: recoverForm.code.trim(),
        new_password: recoverForm.newPassword,
      })

      setAuthenticatedUser(response.user)
      navigate(resolveAuthSuccessPath(location), { replace: true })
    } catch (requestError) {
      setRecoverError(getApiErrorMessage(requestError, 'Не удалось сохранить новый пароль.'))
    } finally {
      setIsRecoverConfirmSubmitting(false)
    }
  }

  async function handleRecoverResend() {
    setRecoverError(null)
    setRecoverInfo(null)
    setIsRecoverResending(true)

    try {
      const response = await resendPasswordReset({
        email: recoverForm.email.trim(),
      })
      setRecoverInfo(response.message)
      setRecoverCooldown(response.resend_available_in ?? 0)
    } catch (requestError) {
      setRecoverError(getApiErrorMessage(requestError, 'Не удалось отправить код повторно.'))
      const resendAvailableIn = getApiErrorNumber(requestError, 'resend_available_in')
      if (resendAvailableIn) {
        setRecoverCooldown(resendAvailableIn)
      }
    } finally {
      setIsRecoverResending(false)
    }
  }

  const title =
    view === 'login'
      ? 'Войти в аккаунт'
      : view === 'register'
        ? 'Создать аккаунт'
        : 'Восстановить пароль'

  const description =
    view === 'login'
      ? 'Сохраните избранное, покупки и настройки профиля в одном месте.'
      : view === 'register'
        ? 'Регистрация занимает меньше минуты. Подтверждение придёт кодом на email.'
        : 'Отправим код на почту, после чего можно будет сразу задать новый пароль.'

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
          {view === 'recover' ? (
            <button
              type="button"
              onClick={() => switchView('login')}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm font-semibold text-slate-100 transition hover:border-brand-300/50 hover:bg-brand-500/10"
            >
              <ArrowLeft size={16} />
              Вернуться ко входу
            </button>
          ) : (
            <div className="grid grid-cols-2 gap-2 rounded-[20px] border border-white/10 bg-slate-950/50 p-1">
              <TabButton active={view === 'login'} onClick={() => switchView('login')}>
                Вход
              </TabButton>
              <TabButton active={view === 'register'} onClick={() => switchView('register')}>
                Регистрация
              </TabButton>
            </div>
          )}

          {view !== 'recover' ? (
            <div className="mt-5">
              <SocialAuthPanel nextPath={oauthReturnPath} compact />
            </div>
          ) : null}

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
                  <button
                    type="button"
                    onClick={openRecoveryView}
                    className="text-brand-200 transition hover:text-white"
                  >
                    Забыли пароль?
                  </button>
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
          ) : null}

          {view === 'register' ? (
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
                  <p className="mt-2 text-xs leading-6 text-slate-400">К этому email будут привязаны все покупки.</p>
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
          ) : null}

          {view === 'recover' ? (
            <div className="mt-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-white">Восстановление по email</p>
                  <p className="mt-1 text-sm text-slate-400">
                    {recoverStep === 'request'
                      ? 'Сначала отправим код подтверждения на почту аккаунта.'
                      : 'Введите код из письма и сразу задайте новый пароль.'}
                  </p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-100">
                  <KeyRound size={18} />
                </div>
              </div>

              <form
                className="mt-5 space-y-4"
                onSubmit={recoverStep === 'request' ? handleRecoverRequestSubmit : handleRecoverConfirmSubmit}
              >
                <TextField
                  label="Email"
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
                  value={recoverForm.email}
                  onChange={(event) => updateRecoverField('email', event.target.value)}
                  required
                />

                {recoverStep === 'confirm' ? (
                  <>
                    <TextField
                      label="Код из письма"
                      hint="6 цифр"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      placeholder="123456"
                      value={recoverForm.code}
                      onChange={(event) => updateRecoverField('code', event.target.value.replace(/\D/g, '').slice(0, 6))}
                      required
                    />

                    <div className="grid gap-4 md:grid-cols-2">
                      <TextField
                        label="Новый пароль"
                        type="password"
                        autoComplete="new-password"
                        hint="Минимум 8 символов"
                        placeholder="Введите новый пароль"
                        value={recoverForm.newPassword}
                        onChange={(event) => updateRecoverField('newPassword', event.target.value)}
                        required
                      />
                      <TextField
                        label="Повторите пароль"
                        type="password"
                        autoComplete="new-password"
                        placeholder="Повторите новый пароль"
                        value={recoverForm.confirmPassword}
                        onChange={(event) => updateRecoverField('confirmPassword', event.target.value)}
                        required
                      />
                    </div>
                  </>
                ) : null}

                {recoverInfo ? <div className="auth-alert auth-alert-info">{recoverInfo}</div> : null}
                {recoverError ? <div className="auth-alert auth-alert-error">{recoverError}</div> : null}

                {recoverStep === 'confirm' ? (
                  <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
                    Код действует 10 минут. После сохранения нового пароля мы сразу авторизуем вас в аккаунте.
                  </div>
                ) : null}

                <div className="flex flex-col gap-3 sm:flex-row">
                  {recoverStep === 'request' ? (
                    <button
                      type="submit"
                      disabled={isRecoverRequestSubmitting}
                      className="btn-primary flex-1 disabled:opacity-60"
                    >
                      <ShieldCheck size={16} />
                      {isRecoverRequestSubmitting ? 'Отправляем код...' : 'Получить код'}
                    </button>
                  ) : (
                    <>
                      <button
                        type="submit"
                        disabled={isRecoverConfirmSubmitting}
                        className="btn-primary flex-1 disabled:opacity-60"
                      >
                        <ShieldCheck size={16} />
                        {isRecoverConfirmSubmitting ? 'Сохраняем пароль...' : 'Сохранить новый пароль'}
                      </button>
                      <button
                        type="button"
                        onClick={handleRecoverResend}
                        disabled={isRecoverResending || recoverCooldown > 0 || !recoverForm.email.trim()}
                        className="btn-secondary flex-1 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <RotateCcw size={16} />
                        {recoverCooldown > 0
                          ? `Повторно через ${formatCooldown(recoverCooldown)}`
                          : isRecoverResending
                            ? 'Отправляем...'
                            : 'Отправить код ещё раз'}
                      </button>
                    </>
                  )}
                </div>
              </form>

              <div className="mt-5 flex flex-col gap-3 rounded-[24px] border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-300">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span>Если вспомнили пароль, можно сразу вернуться к обычному входу.</span>
                  <button
                    type="button"
                    onClick={() => switchView('login')}
                    className="font-semibold text-brand-200 transition hover:text-white"
                  >
                    Перейти ко входу
                  </button>
                </div>

                {recoverStep === 'confirm' ? (
                  <button
                    type="button"
                    onClick={() => {
                      setRecoverStep('request')
                      setRecoverError(null)
                      setRecoverInfo(null)
                    }}
                    className="self-start font-semibold text-slate-300 transition hover:text-white"
                  >
                    Изменить email
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
