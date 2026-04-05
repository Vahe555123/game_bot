import { ChevronRight, MailCheck, UserRoundPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell } from '../components/auth/AuthShell'
import { SelectField, TextField } from '../components/auth/FormField'
import { SocialAuthPanel } from '../components/auth/SocialAuthPanel'
import { register } from '../services/auth'
import { getApiErrorMessage } from '../utils/apiErrors'

type RegisterFormState = {
  email: string
  password: string
  confirmPassword: string
  username: string
  firstName: string
  lastName: string
  preferredRegion: string
  showUkrainePrices: boolean
  showTurkeyPrices: boolean
  showIndiaPrices: boolean
  paymentEmail: string
  platform: string
  psnEmail: string
}

const regionOptions = [
  { value: 'UA', label: 'Украина (UA)' },
  { value: 'TR', label: 'Турция (TR)' },
  { value: 'IN', label: 'Индия (IN)' },
]

const platformOptions = [
  { value: '', label: 'Не выбрано' },
  { value: 'PS4', label: 'PS4' },
  { value: 'PS5', label: 'PS5' },
]

const defaultFormState: RegisterFormState = {
  email: '',
  password: '',
  confirmPassword: '',
  username: '',
  firstName: '',
  lastName: '',
  preferredRegion: 'UA',
  showUkrainePrices: false,
  showTurkeyPrices: true,
  showIndiaPrices: false,
  paymentEmail: '',
  platform: '',
  psnEmail: '',
}

const regionToggleFields: Array<{
  field: 'showUkrainePrices' | 'showTurkeyPrices' | 'showIndiaPrices'
  label: string
}> = [
  { field: 'showUkrainePrices', label: 'Украина' },
  { field: 'showTurkeyPrices', label: 'Турция' },
  { field: 'showIndiaPrices', label: 'Индия' },
]

export function RegisterPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<RegisterFormState>(defaultFormState)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField<K extends keyof RegisterFormState>(field: K, value: RegisterFormState[K]) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    if (form.password !== form.confirmPassword) {
      setError('Пароли не совпадают.')
      return
    }

    setIsSubmitting(true)

    try {
      const response = await register({
        email: form.email.trim(),
        password: form.password,
        username: form.username.trim() || undefined,
        first_name: form.firstName.trim() || undefined,
        last_name: form.lastName.trim() || undefined,
        preferred_region: form.preferredRegion,
        show_ukraine_prices: form.showUkrainePrices,
        show_turkey_prices: form.showTurkeyPrices,
        show_india_prices: form.showIndiaPrices,
        payment_email: form.paymentEmail.trim() || undefined,
        platform: form.platform || undefined,
        psn_email: form.psnEmail.trim() || undefined,
      })

      navigate(`/verify-email?email=${encodeURIComponent(form.email.trim())}`, {
        replace: true,
        state: {
          message: response.message,
          resendAvailableIn: response.resend_available_in ?? null,
        },
      })
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Не удалось создать аккаунт.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Регистрация"
      title="Создай профиль сайта"
      description="Регистрация повторяет логику бота: email, предпочтительный регион, платформа и дополнительные поля для будущих покупок."
      asideTitle="Что будет дальше"
      asideText="После отправки формы мы отправим 6-значный код на почту. Он живёт 10 минут, а повторную отправку можно сделать с cooldown."
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-brand-200/80">Новый аккаунт</p>
          <h2 className="mt-3 text-3xl text-white">Регистрация в стиле miniapp</h2>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-100">
          <UserRoundPlus size={20} />
        </div>
      </div>

      <form className="mt-8 space-y-7" onSubmit={handleSubmit}>
        <div className="grid gap-4 md:grid-cols-2">
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={form.email}
            onChange={(event) => updateField('email', event.target.value)}
            required
          />
          <TextField
            label="Username"
            placeholder="@nickname"
            value={form.username}
            onChange={(event) => updateField('username', event.target.value)}
          />
          <TextField
            label="Имя"
            autoComplete="given-name"
            placeholder="Имя"
            value={form.firstName}
            onChange={(event) => updateField('firstName', event.target.value)}
          />
          <TextField
            label="Фамилия"
            autoComplete="family-name"
            placeholder="Фамилия"
            value={form.lastName}
            onChange={(event) => updateField('lastName', event.target.value)}
          />
          <TextField
            label="Пароль"
            type="password"
            autoComplete="new-password"
            hint="Минимум 8 символов"
            placeholder="Создай пароль"
            value={form.password}
            onChange={(event) => updateField('password', event.target.value)}
            required
          />
          <TextField
            label="Повтори пароль"
            type="password"
            autoComplete="new-password"
            placeholder="Повтори пароль"
            value={form.confirmPassword}
            onChange={(event) => updateField('confirmPassword', event.target.value)}
            required
          />
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <SelectField
            label="Основной регион"
            value={form.preferredRegion}
            onChange={(event) => updateField('preferredRegion', event.target.value)}
            options={regionOptions}
          />
          <SelectField
            label="Платформа"
            value={form.platform}
            onChange={(event) => updateField('platform', event.target.value)}
            options={platformOptions}
          />
          <TextField
            label="Платёжный email"
            type="email"
            placeholder="Для покупок"
            value={form.paymentEmail}
            onChange={(event) => updateField('paymentEmail', event.target.value)}
          />
        </div>

        <TextField
          label="PSN email"
          type="email"
          placeholder="Если уже есть"
          value={form.psnEmail}
          onChange={(event) => updateField('psnEmail', event.target.value)}
        />

        <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-white">Показывать цены регионов</p>
              <p className="mt-1 text-sm text-slate-400">
                Это повторяет настройки профиля из бота и сразу готовит сайт под твои регионы.
              </p>
            </div>
            <MailCheck className="text-brand-200" size={20} />
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {regionToggleFields.map(({ field, label }) => {
              const checked = form[field]

              return (
                <label
                  key={field}
                  className={`flex cursor-pointer items-center justify-between rounded-[22px] border px-4 py-4 transition ${
                    checked
                      ? 'border-brand-300/60 bg-brand-500/10 text-white'
                      : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20'
                  }`}
                >
                  <span className="text-sm font-semibold">{label}</span>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => updateField(field, event.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-slate-950 text-brand-400"
                  />
                </label>
              )
            })}
          </div>
        </div>

        {error ? <div className="auth-alert auth-alert-error">{error}</div> : null}

        <div className="flex flex-col gap-3 sm:flex-row">
          <button type="submit" disabled={isSubmitting} className="btn-primary flex-1 disabled:opacity-60">
            <ChevronRight size={16} />
            {isSubmitting ? 'Отправляем код...' : 'Зарегистрироваться'}
          </button>
          <Link to="/login" className="btn-secondary flex-1 text-center">
            Уже есть аккаунт
          </Link>
        </div>
      </form>

      <div className="mt-6">
        <SocialAuthPanel nextPath="/profile" />
      </div>
    </AuthShell>
  )
}
