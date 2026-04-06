import { Clock3, MailCheck, RotateCcw } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthShell } from '../components/auth/AuthShell'
import { TextField } from '../components/auth/FormField'
import { useAuth } from '../context/AuthContext'
import { resendCode, verifyEmail } from '../services/auth'
import { getApiErrorMessage, getApiErrorNumber } from '../utils/apiErrors'

type LocationState = {
  message?: string
  resendAvailableIn?: number | null
}

function formatCooldown(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remain = seconds % 60
  return `${minutes}:${String(remain).padStart(2, '0')}`
}

export function VerifyEmailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { setAuthenticatedUser } = useAuth()
  const locationState = (location.state || {}) as LocationState

  const [email, setEmail] = useState(searchParams.get('email') || '')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(locationState.message || null)
  const [cooldown, setCooldown] = useState(locationState.resendAvailableIn ?? 0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isResending, setIsResending] = useState(false)

  useEffect(() => {
    if (cooldown <= 0) {
      return undefined
    }

    const timerId = window.setInterval(() => {
      setCooldown((current) => (current <= 1 ? 0 : current - 1))
    }, 1000)

    return () => {
      window.clearInterval(timerId)
    }
  }, [cooldown])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setInfo(null)
    setIsSubmitting(true)

    try {
      const response = await verifyEmail({
        email: email.trim(),
        code: code.trim(),
      })

      setAuthenticatedUser(response.user)
      navigate('/profile', { replace: true })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Не удалось подтвердить email.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleResend() {
    setError(null)
    setInfo(null)
    setIsResending(true)

    try {
      const response = await resendCode({
        email: email.trim(),
      })

      setInfo(response.message)
      setCooldown(response.resend_available_in ?? 0)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Не удалось отправить код повторно.'))
      const resendAvailableIn = getApiErrorNumber(requestError, 'resend_available_in')
      if (resendAvailableIn) {
        setCooldown(resendAvailableIn)
      }
    } finally {
      setIsResending(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Подтверждение email"
      title="Введи 6-значный код"
      description="Код приходит на почту и действует 10 минут. После подтверждения мы сразу откроем твой личный профиль."
      asideTitle="Resend уже готов"
      asideText="Если письмо не пришло сразу, код можно отправить ещё раз. Cooldown и сообщения об ошибках уже подключены к API."
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-brand-200/80">Шаг 2</p>
          <h2 className="mt-3 text-3xl text-white">Подтверждение регистрации</h2>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-100">
          <MailCheck size={20} />
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
          label="Код из письма"
          hint="6 цифр"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          placeholder="123456"
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
          required
        />

        {info ? <div className="auth-alert auth-alert-info">{info}</div> : null}
        {error ? <div className="auth-alert auth-alert-error">{error}</div> : null}

        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
          <div className="flex items-center gap-3">
            <Clock3 size={16} className="text-brand-200" />
            <span>Код действует 10 минут и хранится только в защищённом виде.</span>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <button type="submit" disabled={isSubmitting} className="btn-primary flex-1 disabled:opacity-60">
            {isSubmitting ? 'Проверяем код...' : 'Подтвердить email'}
          </button>
          <button
            type="button"
            onClick={handleResend}
            disabled={isResending || cooldown > 0 || !email.trim()}
            className="btn-secondary flex-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw size={16} />
            {cooldown > 0 ? `Повторно через ${formatCooldown(cooldown)}` : isResending ? 'Отправляем...' : 'Отправить ещё раз'}
          </button>
        </div>
      </form>

      <div className="mt-6 flex flex-col gap-3 rounded-[24px] border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-300 md:flex-row md:items-center md:justify-between">
        <span>Если аккаунт уже подтверждён, можно сразу войти по email и паролю.</span>
        <Link to="/?auth=login" className="font-semibold text-brand-200 transition hover:text-white">
          Перейти ко входу
        </Link>
      </div>
    </AuthShell>
  )
}
