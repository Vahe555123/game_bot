import { Globe, LoaderCircle, MessageCircleMore } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { getAuthProviders, getOAuthStartUrl, telegramLogin } from '../../services/auth'
import type { AuthProvidersResponse, TelegramAuthPayload } from '../../types/auth'
import { getApiErrorMessage } from '../../utils/apiErrors'

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramAuthPayload) => void
  }
}

type SocialAuthPanelProps = {
  nextPath?: string
  compact?: boolean
}

function ProviderButton({
  label,
  onClick,
  icon,
  compact = false,
}: {
  label: string
  onClick: () => void
  icon: ReactNode
  compact?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center justify-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-white transition hover:border-brand-300/50 hover:bg-brand-500/10 ${
        compact ? 'min-h-[48px] py-3' : 'py-3.5'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

export function SocialAuthPanel({ nextPath = '/profile', compact = false }: SocialAuthPanelProps) {
  const navigate = useNavigate()
  const { setAuthenticatedUser } = useAuth()
  const telegramContainerRef = useRef<HTMLDivElement | null>(null)
  const [providers, setProviders] = useState<AuthProvidersResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isTelegramLoading, setIsTelegramLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    ;(async () => {
      try {
        const response = await getAuthProviders()
        if (!ignore) {
          setProviders(response)
        }
      } catch {
        if (!ignore) {
          setProviders(null)
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    if (!providers?.telegram_enabled || !providers.telegram_bot_username || !telegramContainerRef.current) {
      return undefined
    }

    const callbackName = 'onTelegramAuth'
    window[callbackName] = async (user: TelegramAuthPayload) => {
      setError(null)
      setIsTelegramLoading(true)

      try {
        const response = await telegramLogin(user)
        setAuthenticatedUser(response.user)
        navigate(nextPath, { replace: true })
      } catch (requestError) {
        setError(getApiErrorMessage(requestError, 'Не удалось войти через Telegram.'))
      } finally {
        setIsTelegramLoading(false)
      }
    }

    const container = telegramContainerRef.current
    container.innerHTML = ''

    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.async = true
    script.setAttribute('data-telegram-login', providers.telegram_bot_username)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-radius', '18')
    script.setAttribute('data-userpic', 'false')
    script.setAttribute('data-request-access', 'write')
    script.setAttribute('data-onauth', `${callbackName}(user)`)

    container.appendChild(script)

    return () => {
      delete window[callbackName]
      container.innerHTML = ''
    }
  }, [navigate, nextPath, providers, setAuthenticatedUser])

  function beginProviderLogin(provider: 'google' | 'vk') {
    window.location.href = getOAuthStartUrl(provider, nextPath)
  }

  if (isLoading) {
    return (
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-300">
        <div className="flex items-center gap-3">
          <LoaderCircle size={16} className="animate-spin text-brand-200" />
          <span>{compact ? 'Проверяем быстрый вход...' : 'Проверяем доступные способы входа...'}</span>
        </div>
      </div>
    )
  }

  if (!providers || (!providers.google_enabled && !providers.vk_enabled && !providers.telegram_enabled)) {
    return null
  }

  return (
    <div className="space-y-4 rounded-[26px] border border-white/10 bg-white/[0.03] p-5">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-brand-200/80">Быстрый вход</p>
        <p className="mt-2 text-sm text-slate-300">
          {compact
            ? 'Можно войти через внешние сервисы, без отдельной ручной регистрации.'
            : 'Можно войти не только по email и паролю, но и через внешние провайдеры.'}
        </p>
      </div>

      <div className={`grid gap-3 ${compact ? 'md:grid-cols-2' : ''}`}>
        {providers.google_enabled ? (
          <ProviderButton
            label="Войти через Google"
            onClick={() => beginProviderLogin('google')}
            icon={<Globe size={18} />}
            compact={compact}
          />
        ) : null}

        {providers.vk_enabled ? (
          <ProviderButton
            label="Войти через VK"
            onClick={() => beginProviderLogin('vk')}
            icon={<span className="text-base font-bold">VK</span>}
            compact={compact}
          />
        ) : null}

        {providers.telegram_enabled ? (
          <div
            className={`rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-4 ${
              compact ? 'md:col-span-2' : ''
            }`}
          >
            <div className="mb-3 flex items-center gap-3 text-sm font-semibold text-white">
              <MessageCircleMore size={18} />
              <span>Войти через Telegram</span>
            </div>
            <div ref={telegramContainerRef} className="min-h-[52px]" />
            {isTelegramLoading ? (
              <div className="mt-3 flex items-center gap-2 text-sm text-slate-300">
                <LoaderCircle size={16} className="animate-spin text-brand-200" />
                <span>Подтверждаем вход через Telegram...</span>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {error ? <div className="auth-alert auth-alert-error">{error}</div> : null}
    </div>
  )
}
