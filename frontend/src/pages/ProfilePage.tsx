import {
  ArrowUpRight,
  Copy,
  ExternalLink,
  Globe2,
  Heart,
  LogOut,
  Mail,
  Save,
  ShieldCheck,
  ShoppingBag,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { buildAuthModalPath } from '../components/auth/authModalState'
import { useAuth } from '../context/AuthContext'
import { useFavorites } from '../context/FavoritesContext'
import { getProfile, updateProfilePreferences, updateProfilePsnAccount } from '../services/auth'
import { listPurchases } from '../services/purchases'
import type {
  ProfilePreferencesPayload,
  ProfilePSNAccountPayload,
  SiteProfileResponse,
  SitePSNAccount,
  SitePSNRegion,
} from '../types/auth'
import type { PurchaseOrder } from '../types/purchase'
import { getApiErrorMessage } from '../utils/apiErrors'
import { getDualCurrencyPriceDisplay } from '../utils/format'

type SaveState = {
  loading: boolean
  message: string | null
  error: boolean
}

type PsnDraft = {
  platform: '' | 'PS4' | 'PS5'
  psn_email: string
  psn_password: string
}

type PurchaseDayFilterValue = 'all' | '7' | '30' | '90'

const PROFILE_SECTIONS = [
  { id: 'favorites-section', label: 'Избранное', icon: Heart },
  { id: 'purchases-section', label: 'Покупки', icon: ShoppingBag },
  { id: 'region-section', label: 'Регион игр', icon: Globe2 },
  { id: 'psn-section', label: 'PS аккаунт', icon: ShieldCheck },
  { id: 'purchase-email-section', label: 'Email покупки', icon: Mail },
] as const

const REGION_OPTIONS = [
  { value: 'TR', label: 'Турция' },
  { value: 'UA', label: 'Украина' },
  { value: 'IN', label: 'Индия' },
] as const

const REGION_LABELS: Record<string, string> = {
  TR: 'Турция',
  UA: 'Украина',
  IN: 'Индия',
}

const PURCHASE_DAY_FILTERS: Array<{ value: PurchaseDayFilterValue; label: string }> = [
  { value: 'all', label: 'Все' },
  { value: '7', label: '7 дней' },
  { value: '30', label: '30 дней' },
  { value: '90', label: '90 дней' },
]

const EMPTY_SAVE_STATE: SaveState = {
  loading: false,
  message: null,
  error: false,
}

function resolvePurchaseFilterDays(filter: PurchaseDayFilterValue): number | undefined {
  if (filter === 'all') {
    return undefined
  }

  return Number(filter)
}

function createEmptyAccount(region: SitePSNRegion): SitePSNAccount {
  return {
    region,
    platform: null,
    psn_email: null,
    has_password: false,
    has_backup_code: false,
    updated_at: null,
  }
}

function buildPsnDraft(account: SitePSNAccount | undefined): PsnDraft {
  return {
    platform: account?.platform ?? '',
    psn_email: account?.psn_email ?? '',
    psn_password: '',
  }
}

function normalizeProfile(response: SiteProfileResponse): SiteProfileResponse {
  return {
    ...response,
    psn_accounts: {
      UA: response.psn_accounts.UA ?? createEmptyAccount('UA'),
      TR: response.psn_accounts.TR ?? createEmptyAccount('TR'),
    },
  }
}

function normalizePreferredRegion(value?: string | null): ProfilePreferencesPayload['preferred_region'] {
  if (value === 'UA' || value === 'TR' || value === 'IN') {
    return value
  }

  return 'TR'
}

function SaveNotice({ state }: { state: SaveState }) {
  if (!state.message) {
    return null
  }

  return <div className={`auth-alert ${state.error ? 'auth-alert-error' : 'auth-alert-info'}`}>{state.message}</div>
}

function SectionCard({
  id,
  title,
  description,
  action,
  children,
}: {
  id: string
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section id={id} className="panel-soft rounded-[30px] p-6 md:p-7">
      <div className="flex flex-col gap-4 border-b border-white/8 pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl text-white">{title}</h2>
          {description ? <p className="mt-2 text-sm leading-7 text-slate-400">{description}</p> : null}
        </div>
        {action}
      </div>

      <div className="pt-5">{children}</div>
    </section>
  )
}

function PurchaseCard({
  order,
  onCopyLink,
}: {
  order: PurchaseOrder
  onCopyLink: (order: PurchaseOrder) => Promise<void>
}) {
  const orderPriceDisplay = getDualCurrencyPriceDisplay(order.local_price, order.currency_code, order.price_rub)

  return (
    <article className="rounded-[26px] border border-white/10 bg-slate-950/45 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="pill bg-white/5 text-slate-300">{REGION_LABELS[order.product_region] || order.product_region}</span>
            {order.use_ps_plus ? <span className="pill border-amber-300/20 bg-amber-500/12 text-amber-50">PS Plus</span> : null}
          </div>

          <div>
            <h3 className="text-xl text-white">{order.product_name}</h3>
            <p className="mt-2 text-sm text-slate-400">
              {order.order_number} • {new Date(order.created_at).toLocaleString('ru-RU')}
            </p>
          </div>
        </div>

        <div className="text-left lg:text-right">
          <p className="text-sm text-slate-400">Стоимость</p>
          <p className="mt-1 text-xl font-semibold text-white">{orderPriceDisplay.primary}</p>
          {orderPriceDisplay.secondary ? (
            <p className="mt-1 text-sm text-slate-500">{orderPriceDisplay.secondary}</p>
          ) : null}
        </div>
      </div>

      {order.payment_url ? (
        <div className="mt-5 rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Ссылка на оплату</p>
          <p className="mt-3 break-all text-sm leading-7 text-white">{order.payment_url}</p>

          <div className="mt-4 flex flex-wrap gap-3">
            <a href={order.payment_url} className="btn-primary">
              <ExternalLink size={16} />
              Открыть ссылку
            </a>
            <button type="button" onClick={() => onCopyLink(order)} className="btn-secondary">
              <Copy size={16} />
              Скопировать
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-[24px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm leading-7 text-slate-400">
          Для этой покупки ссылка не сохранена.
        </div>
      )}
    </article>
  )
}

export function ProfilePage() {
  const navigate = useNavigate()
  const { favorites } = useFavorites()
  const { logoutUser, setAuthenticatedUser } = useAuth()

  const [profile, setProfile] = useState<SiteProfileResponse | null>(null)
  const [orders, setOrders] = useState<PurchaseOrder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [purchasesLoading, setPurchasesLoading] = useState(true)
  const [purchaseFilter, setPurchaseFilter] = useState<PurchaseDayFilterValue>('all')
  const [activePsnRegion, setActivePsnRegion] = useState<SitePSNRegion>('UA')
  const [regionDraft, setRegionDraft] = useState<ProfilePreferencesPayload['preferred_region']>('TR')
  const [paymentEmailDraft, setPaymentEmailDraft] = useState('')
  const [psnDrafts, setPsnDrafts] = useState<Record<SitePSNRegion, PsnDraft>>({
    UA: buildPsnDraft(undefined),
    TR: buildPsnDraft(undefined),
  })

  const [regionSaveState, setRegionSaveState] = useState<SaveState>(EMPTY_SAVE_STATE)
  const [paymentSaveState, setPaymentSaveState] = useState<SaveState>(EMPTY_SAVE_STATE)
  const [psnSaveState, setPsnSaveState] = useState<SaveState>(EMPTY_SAVE_STATE)
  const [purchaseSaveState, setPurchaseSaveState] = useState<SaveState>(EMPTY_SAVE_STATE)

  useEffect(() => {
    let ignore = false

    ;(async () => {
      try {
        const profileResponse = await getProfile()
        const normalizedProfile = normalizeProfile(profileResponse)

        if (!ignore) {
          setProfile(normalizedProfile)
          setAuthenticatedUser(normalizedProfile.user)
          setRegionDraft(normalizePreferredRegion(normalizedProfile.user.preferred_region))
          setPaymentEmailDraft(normalizedProfile.user.payment_email ?? '')
          setPsnDrafts({
            UA: buildPsnDraft(normalizedProfile.psn_accounts.UA),
            TR: buildPsnDraft(normalizedProfile.psn_accounts.TR),
          })
        }
      } catch {
        if (!ignore) {
          setProfile(null)
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
  }, [setAuthenticatedUser])

  useEffect(() => {
    let ignore = false

    ;(async () => {
      setPurchasesLoading(true)
      setPurchaseSaveState({ loading: false, message: null, error: false })

      try {
        const purchasesResponse = await listPurchases(resolvePurchaseFilterDays(purchaseFilter))
        if (!ignore) {
          setOrders(purchasesResponse.orders)
        }
      } catch (error) {
        if (!ignore) {
          setOrders([])
          setPurchaseSaveState({
            loading: false,
            message: getApiErrorMessage(error, 'Не удалось загрузить покупки.'),
            error: true,
          })
        }
      } finally {
        if (!ignore) {
          setPurchasesLoading(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [purchaseFilter])

  async function handleLogout() {
    await logoutUser()
    navigate(buildAuthModalPath({ pathname: '/', search: '', hash: '' }, 'login'), { replace: true })
  }

  function applyProfile(response: SiteProfileResponse) {
    const nextProfile = normalizeProfile(response)
    setProfile(nextProfile)
    setAuthenticatedUser(nextProfile.user)
    setRegionDraft(normalizePreferredRegion(nextProfile.user.preferred_region))
    setPaymentEmailDraft(nextProfile.user.payment_email ?? '')
    setPsnDrafts((current) => ({
      UA: {
        platform: nextProfile.psn_accounts.UA.platform ?? current.UA.platform,
        psn_email: nextProfile.psn_accounts.UA.psn_email ?? current.UA.psn_email,
        psn_password: '',
      },
      TR: {
        platform: nextProfile.psn_accounts.TR.platform ?? current.TR.platform,
        psn_email: nextProfile.psn_accounts.TR.psn_email ?? current.TR.psn_email,
        psn_password: '',
      },
    }))
  }

  async function saveRegion() {
    setRegionSaveState({ loading: true, message: null, error: false })

    try {
      const response = await updateProfilePreferences({
        preferred_region: regionDraft,
        payment_email: paymentEmailDraft.trim() ? paymentEmailDraft.trim() : null,
      })

      applyProfile(response)
      setRegionSaveState({
        loading: false,
        message: 'Регион игр сохранен.',
        error: false,
      })
    } catch (error) {
      setRegionSaveState({
        loading: false,
        message: getApiErrorMessage(error, 'Не удалось сохранить регион.'),
        error: true,
      })
    }
  }

  async function savePaymentEmail() {
    setPaymentSaveState({ loading: true, message: null, error: false })

    try {
      const response = await updateProfilePreferences({
        preferred_region: regionDraft,
        payment_email: paymentEmailDraft.trim() ? paymentEmailDraft.trim() : null,
      })

      applyProfile(response)
      setPaymentSaveState({
        loading: false,
        message: 'Email для покупки сохранен.',
        error: false,
      })
    } catch (error) {
      setPaymentSaveState({
        loading: false,
        message: getApiErrorMessage(error, 'Не удалось сохранить email для покупки.'),
        error: true,
      })
    }
  }

  function updatePsnDraft(region: SitePSNRegion, patch: Partial<PsnDraft>) {
    setPsnDrafts((current) => ({
      ...current,
      [region]: {
        ...current[region],
        ...patch,
      },
    }))
  }

  async function savePsnAccount() {
    const draft = psnDrafts[activePsnRegion]
    const payload: ProfilePSNAccountPayload = {
      platform: draft.platform || null,
      psn_email: draft.psn_email.trim() || null,
      psn_password: draft.psn_password.trim() || null,
    }

    setPsnSaveState({ loading: true, message: null, error: false })

    try {
      const response = await updateProfilePsnAccount(activePsnRegion, payload)
      applyProfile(response)
      setPsnSaveState({
        loading: false,
        message: `Данные ${activePsnRegion === 'UA' ? 'Украины' : 'Турции'} сохранены.`,
        error: false,
      })
    } catch (error) {
      setPsnSaveState({
        loading: false,
        message: getApiErrorMessage(error, 'Не удалось сохранить PS аккаунт.'),
        error: true,
      })
    }
  }

  async function handleCopyPaymentLink(order: PurchaseOrder) {
    if (!order.payment_url) {
      return
    }

    try {
      await navigator.clipboard.writeText(order.payment_url)
      setPurchaseSaveState({
        loading: false,
        message: `Ссылка для ${order.order_number} скопирована.`,
        error: false,
      })
    } catch {
      setPurchaseSaveState({
        loading: false,
        message: 'Не удалось скопировать ссылку автоматически.',
        error: true,
      })
    }
  }

  if (isLoading) {
    return (
      <div className="container py-10 md:py-14">
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-6">
            <div className="panel-soft h-36 animate-pulse rounded-[30px]" />
            <div className="panel-soft h-[28rem] animate-pulse rounded-[30px]" />
            <div className="panel-soft h-56 animate-pulse rounded-[30px]" />
            <div className="panel-soft h-[30rem] animate-pulse rounded-[30px]" />
            <div className="panel-soft h-64 animate-pulse rounded-[30px]" />
          </div>
          <div className="panel-soft h-72 animate-pulse rounded-[30px]" />
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="container py-10 md:py-14">
        <div className="panel-soft rounded-[30px] px-6 py-12 text-center text-slate-300">Не удалось загрузить профиль.</div>
      </div>
    )
  }

  const currentAccount = profile.psn_accounts[activePsnRegion] ?? createEmptyAccount(activePsnRegion)
  const currentDraft = psnDrafts[activePsnRegion]

  return (
    <div className="container py-10 md:py-14">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-6">
          <SectionCard
            id="favorites-section"
            title="Избранное"
            description="Все товары, которые ты отметил сердцем, собраны в отдельном разделе."
            action={
              <Link to="/favorites" className="btn-secondary">
                <ArrowUpRight size={16} />
                Открыть
              </Link>
            }
          >
            <div className="flex flex-col gap-4 rounded-[26px] border border-white/10 bg-slate-950/45 p-5 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm text-slate-400">Сохраненные игры</p>
                <p className="mt-2 text-4xl font-semibold text-white">{favorites.length}</p>
              </div>
              <div className="rounded-[22px] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-300">
                Быстрый доступ ко всем товарам, которые хочешь держать под рукой.
              </div>
            </div>
          </SectionCard>

          <SectionCard
            id="purchases-section"
            title="Покупки"
            description="Здесь сохраняются дата покупки и сама ссылка на оплату."
          >
            <div className="space-y-4">
              <SaveNotice state={purchaseSaveState} />

              <div className="flex flex-wrap gap-2">
                {PURCHASE_DAY_FILTERS.map((option) => {
                  const active = purchaseFilter === option.value

                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setPurchaseFilter(option.value)}
                      className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                        active
                          ? 'border-brand-300/50 bg-brand-500/12 text-white shadow-glow'
                          : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-brand-300/30'
                      }`}
                    >
                      {option.label}
                    </button>
                  )
                })}
              </div>

              {purchasesLoading ? (
                <div className="space-y-4">
                  <div className="rounded-[26px] border border-white/10 bg-slate-950/45 p-5">
                    <div className="h-6 w-48 animate-pulse rounded bg-white/10" />
                    <div className="mt-4 h-16 animate-pulse rounded-[20px] bg-white/10" />
                  </div>
                  <div className="rounded-[26px] border border-white/10 bg-slate-950/45 p-5">
                    <div className="h-6 w-56 animate-pulse rounded bg-white/10" />
                    <div className="mt-4 h-16 animate-pulse rounded-[20px] bg-white/10" />
                  </div>
                </div>
              ) : orders.length ? (
                orders.map((order) => (
                  <PurchaseCard key={order.order_number} order={order} onCopyLink={handleCopyPaymentLink} />
                ))
              ) : (
                <div className="rounded-[26px] border border-white/10 bg-slate-950/45 px-5 py-8 text-sm leading-7 text-slate-400">
                  Покупок за выбранный период пока нет.
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard
            id="region-section"
            title="Регион игр"
            description="Можно выбрать только один основной регион для каталога."
          >
            <div className="grid gap-3 md:grid-cols-3">
              {REGION_OPTIONS.map((option) => {
                const active = regionDraft === option.value

                return (
                  <label
                    key={option.value}
                    className={`cursor-pointer rounded-[24px] border px-4 py-4 transition ${
                      active
                        ? 'border-brand-300/50 bg-brand-500/12 text-white shadow-glow'
                        : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-brand-300/30'
                    }`}
                  >
                    <input
                      type="radio"
                      name="preferred-region"
                      value={option.value}
                      checked={active}
                      onChange={() => setRegionDraft(option.value)}
                      className="sr-only"
                    />
                    <span className="text-base font-semibold">{option.label}</span>
                  </label>
                )
              })}
            </div>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <SaveNotice state={regionSaveState} />
              <button type="button" className="btn-primary sm:ml-auto" onClick={saveRegion} disabled={regionSaveState.loading}>
                <Save size={16} />
                {regionSaveState.loading ? 'Сохраняем...' : 'Сохранить регион'}
              </button>
            </div>
          </SectionCard>

          <SectionCard
            id="psn-section"
            title="PS аккаунт"
            description="Украина и Турция настраиваются отдельно, чтобы можно было быстро оформлять покупку."
          >
            <div className="grid gap-3 sm:grid-cols-2">
              {(['UA', 'TR'] as SitePSNRegion[]).map((region) => {
                const active = activePsnRegion === region
                const account = profile.psn_accounts[region]
                const configured = Boolean(account.psn_email || account.has_password)

                return (
                  <button
                    key={region}
                    type="button"
                    onClick={() => setActivePsnRegion(region)}
                    className={`rounded-[24px] border px-4 py-4 text-left transition ${
                      active
                        ? 'border-brand-300/50 bg-brand-500/12 text-white shadow-glow'
                        : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-brand-300/30'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-lg font-semibold">{region === 'UA' ? 'Украина' : 'Турция'}</span>
                      <span className={`text-xs font-semibold ${configured ? 'text-emerald-300' : 'text-slate-500'}`}>
                        {configured ? 'Настроен' : 'Пусто'}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>

            <div className="mt-6 space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Платформа</label>
                  <select
                    value={currentDraft.platform}
                    onChange={(event) =>
                      updatePsnDraft(activePsnRegion, {
                        platform: (event.target.value as PsnDraft['platform']) || '',
                      })
                    }
                    className="auth-input"
                  >
                    <option value="">Выберите платформу</option>
                    <option value="PS5">PlayStation 5</option>
                    <option value="PS4">PlayStation 4</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">PSN Email</label>
                  <input
                    type="email"
                    value={currentDraft.psn_email}
                    onChange={(event) =>
                      updatePsnDraft(activePsnRegion, {
                        psn_email: event.target.value,
                      })
                    }
                    className="auth-input"
                    placeholder="psn@example.com"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">PSN Пароль</label>
                  <input
                    type="password"
                    value={currentDraft.psn_password}
                    onChange={(event) =>
                      updatePsnDraft(activePsnRegion, {
                        psn_password: event.target.value,
                      })
                    }
                    className="auth-input"
                    placeholder={currentAccount.has_password ? 'Пароль уже сохранен' : 'Введите пароль'}
                  />
                </div>

              </div>

              <div className="flex flex-wrap gap-2">
                {currentAccount.has_password ? (
                  <span className="pill border-emerald-400/20 bg-emerald-500/12 text-emerald-100">Пароль сохранен</span>
                ) : null}
                {currentAccount.updated_at ? (
                  <span className="pill bg-white/5 text-slate-300">
                    Обновлено {new Date(currentAccount.updated_at).toLocaleDateString('ru-RU')}
                  </span>
                ) : null}
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <SaveNotice state={psnSaveState} />
                <button type="button" className="btn-primary sm:ml-auto" onClick={savePsnAccount} disabled={psnSaveState.loading}>
                  <Save size={16} />
                  {psnSaveState.loading ? 'Сохраняем...' : `Сохранить ${activePsnRegion === 'UA' ? 'Украину' : 'Турцию'}`}
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            id="purchase-email-section"
            title="Email для покупки"
            description="Этот email будет автоматически подставляться при создании заказа."
          >
            <div className="rounded-[28px] border border-white/10 bg-slate-950/45 p-5">
              <div className="rounded-[22px] border border-brand-300/15 bg-brand-500/10 px-4 py-4 text-sm leading-7 text-brand-50">
                Этот email будет автоматически заполняться на странице оплаты для всех регионов.
              </div>

              <div className="mt-5">
                <label className="mb-2 block text-sm font-medium text-slate-200">Email для привязки покупки</label>
                <input
                  type="email"
                  value={paymentEmailDraft}
                  onChange={(event) => setPaymentEmailDraft(event.target.value)}
                  className="auth-input"
                  placeholder="email@example.com"
                />
                <p className="mt-3 text-sm text-slate-500">
                  На этот email будут приходить письма по заказу и данные после выдачи.
                </p>
              </div>

              <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <SaveNotice state={paymentSaveState} />
                <button type="button" className="btn-primary sm:ml-auto" onClick={savePaymentEmail} disabled={paymentSaveState.loading}>
                  <Save size={16} />
                  {paymentSaveState.loading ? 'Сохраняем...' : 'Сохранить email'}
                </button>
              </div>
            </div>
          </SectionCard>
        </div>

        <aside className="xl:sticky xl:top-28 xl:self-start">
          <div className="panel-soft rounded-[30px] p-4">
            <div className="space-y-2">
              {PROFILE_SECTIONS.map(({ id, label, icon: Icon }) => (
                <a
                  key={id}
                  href={`#${id}`}
                  className="flex items-center gap-3 rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-brand-300/40 hover:bg-brand-500/10"
                >
                  <Icon size={16} className="text-brand-200" />
                  {label}
                </a>
              ))}
            </div>

            <button type="button" className="btn-secondary mt-4 w-full" onClick={handleLogout}>
              <LogOut size={16} />
              Выйти
            </button>
          </div>
        </aside>
      </div>
    </div>
  )
}
