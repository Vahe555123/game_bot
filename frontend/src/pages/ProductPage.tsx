import {
  AlertCircle,
  ArrowLeft,
  BadgePercent,
  Copy,
  CreditCard,
  ExternalLink,
  Gamepad2,
  Languages,
  LoaderCircle,
  ShieldCheck,
  Star,
} from 'lucide-react'
import { useEffect, useMemo, useState, type MouseEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { FavoriteButton } from '../components/catalog/FavoriteButton'
import { LocalizationBadge } from '../components/catalog/LocalizationBadge'
import { RegionalPriceList } from '../components/catalog/RegionalPriceList'
import { useAuth } from '../context/AuthContext'
import { useFavorites } from '../context/FavoritesContext'
import { mockProducts } from '../data/mockProducts'
import { getProfile } from '../services/auth'
import { fetchProduct } from '../services/catalog'
import { createPurchaseCheckout } from '../services/purchases'
import type { CatalogProduct, ProductRegionPrice } from '../types/catalog'
import type { SiteProfileResponse } from '../types/auth'
import type { PurchaseOrder } from '../types/purchase'
import { getApiErrorDetail, getApiErrorMessage } from '../utils/apiErrors'
import {
  formatRating,
  getDualCurrencyPriceDisplay,
  normalizeImageUrl,
  resolveRegionPresentation,
} from '../utils/format'
import {
  getLocalizationPresentation,
  getProductTitle,
  getVisibleRegionalPrices,
} from '../utils/productPresentation'

type SourceMode = 'api' | 'mock'
type CheckoutFieldName = 'purchase_email' | 'psn_email' | 'psn_password'

type CheckoutFormState = {
  purchaseEmail: string
  platform: '' | 'PS4' | 'PS5'
  psnEmail: string
  psnPassword: string
  backupCode: string
}

const EMPTY_CHECKOUT_FORM: CheckoutFormState = {
  purchaseEmail: '',
  platform: '',
  psnEmail: '',
  psnPassword: '',
  backupCode: '',
}

function buildCheckoutForm(
  profile: SiteProfileResponse | null,
  fallbackUser?: { payment_email?: string | null; platform?: string | null; psn_email?: string | null } | null,
): CheckoutFormState {
  const uaAccount = profile?.psn_accounts?.UA
  const resolvedPlatform =
    uaAccount?.platform === 'PS4' || uaAccount?.platform === 'PS5'
      ? uaAccount.platform
      : fallbackUser?.platform === 'PS4' || fallbackUser?.platform === 'PS5'
        ? fallbackUser.platform
        : ''

  return {
    purchaseEmail: profile?.user.payment_email ?? fallbackUser?.payment_email ?? '',
    platform: resolvedPlatform,
    psnEmail: uaAccount?.psn_email ?? fallbackUser?.psn_email ?? '',
    psnPassword: '',
    backupCode: '',
  }
}

function getMissingCheckoutFields(
  region: string,
  form: CheckoutFormState,
  profile: SiteProfileResponse | null,
): CheckoutFieldName[] {
  const missingFields: CheckoutFieldName[] = []

  if (!form.purchaseEmail.trim() && !profile?.user.payment_email) {
    missingFields.push('purchase_email')
  }

  if (region === 'UA') {
    const hasSavedPsnEmail = Boolean(profile?.psn_accounts?.UA?.psn_email || profile?.user.psn_email)
    const hasSavedPsnPassword = Boolean(profile?.psn_accounts?.UA?.has_password)

    if (!form.psnEmail.trim() && !hasSavedPsnEmail) {
      missingFields.push('psn_email')
    }

    if (!form.psnPassword.trim() && !hasSavedPsnPassword) {
      missingFields.push('psn_password')
    }
  }

  return missingFields
}

function buildHighlights(product: CatalogProduct) {
  const localization = getLocalizationPresentation(product.localizationName)

  return [
    {
      label: 'Издатель',
      value: product.publisher || 'PlayStation Store',
      icon: ShieldCheck,
    },
    {
      label: 'Платформы',
      value: product.platforms || 'PS5 / PS4',
      icon: Gamepad2,
    },
    {
      label: 'Локализация',
      value: localization.fullLabel,
      icon: Languages,
    },
  ]
}

function getCheckoutPriceDisplay(price: ProductRegionPrice, usePsPlus = false) {
  const localValue = usePsPlus && price.psPlusPriceLocal !== null ? price.psPlusPriceLocal : price.priceLocal
  const rubValue = usePsPlus && price.psPlusPriceRub !== null ? price.psPlusPriceRub : price.priceRub

  return getDualCurrencyPriceDisplay(localValue, price.currencyCode, rubValue)
}

function extractPaymentMessage(order: PurchaseOrder | null) {
  if (!order) {
    return null
  }

  const metadata = order.payment_metadata || {}
  const cardInfo = metadata.card_info
  if (cardInfo && typeof cardInfo === 'object' && 'message_ru' in cardInfo && typeof cardInfo.message_ru === 'string') {
    return cardInfo.message_ru
  }

  const topupInfo = metadata.topup_info
  if (topupInfo && typeof topupInfo === 'object' && 'message_ru' in topupInfo && typeof topupInfo.message_ru === 'string') {
    return topupInfo.message_ru
  }

  return null
}

function getPreferredCheckoutRegion(
  availableRegions: string[],
  requestedRegion?: string,
  preferredRegion?: string | null,
) {
  const candidates = [requestedRegion, preferredRegion, 'TR', 'UA', 'IN']
    .filter(Boolean)
    .map((value) => value!.toUpperCase().replace('EN-', '').replace('TRY', 'TR').replace('UAH', 'UA').replace('INR', 'IN'))

  for (const candidate of candidates) {
    if (availableRegions.includes(candidate)) {
      return candidate
    }
  }

  return availableRegions[0] ?? 'TR'
}

function CheckoutDialog({
  open,
  onClose,
  selectedRegion,
  onSelectRegion,
  availablePrices,
  usePsPlus,
  onUsePsPlusChange,
  canUsePsPlus,
  checkoutOrder,
  checkoutLoading,
  profileLoading,
  checkoutForm,
  onCheckoutFormChange,
  missingFields,
  hasSavedPurchaseEmail,
  hasSavedUaPassword,
  checkoutMessage,
  checkoutError,
  onCreateOrder,
  onOpenPayment,
  onCopyPaymentLink,
}: {
  open: boolean
  onClose: () => void
  selectedRegion: string
  onSelectRegion: (region: string) => void
  availablePrices: ProductRegionPrice[]
  usePsPlus: boolean
  onUsePsPlusChange: (value: boolean) => void
  canUsePsPlus: boolean
  checkoutOrder: PurchaseOrder | null
  checkoutLoading: boolean
  profileLoading: boolean
  checkoutForm: CheckoutFormState
  onCheckoutFormChange: <K extends keyof CheckoutFormState>(field: K, value: CheckoutFormState[K]) => void
  missingFields: CheckoutFieldName[]
  hasSavedPurchaseEmail: boolean
  hasSavedUaPassword: boolean
  checkoutMessage: string | null
  checkoutError: string | null
  onCreateOrder: () => Promise<void>
  onOpenPayment: () => void
  onCopyPaymentLink: () => Promise<void>
}) {
  useEffect(() => {
    if (!open || typeof document === 'undefined') {
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [open])

  if (!open) {
    return null
  }

  const selectedPrice = availablePrices.find((item) => item.region === selectedRegion) ?? availablePrices[0]
  const paymentMessage = extractPaymentMessage(checkoutOrder)
  const isUkraineCheckout = selectedRegion === 'UA'
  const selectedPriceDisplay = selectedPrice ? getCheckoutPriceDisplay(selectedPrice, usePsPlus) : null
  const orderPriceDisplay = checkoutOrder
    ? getDualCurrencyPriceDisplay(checkoutOrder.local_price, checkoutOrder.currency_code, checkoutOrder.price_rub)
    : null
  const fieldClassName = (fieldName: CheckoutFieldName) =>
    `auth-input ${missingFields.includes(fieldName) ? 'border-rose-400/40 bg-rose-500/10' : ''}`

  return (
    <div
      className="mt-20 fixed inset-0 z-50 flex items-end justify-center bg-slate-950/72 px-3 py-3 backdrop-blur-md md:items-center md:px-4 md:py-6"
      onClick={onClose}
    >
      <div
        className="mt-20 flex max-h-[calc(100dvh-1.5rem)] w-full max-w-2xl flex-col overflow-hidden rounded-[32px] border border-white/10 bg-[#081321] shadow-card md:mt-0 md:max-h-[90vh]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="shrink-0 border-b border-white/10 px-5 py-4 md:px-6">
          <div className="flex items-center justify-between gap-4">
            <div>
            <p className="text-xs uppercase tracking-[0.28em] text-brand-200/80">Покупка</p>
            <h2 className="mt-1 text-2xl text-white">{checkoutOrder ? 'Заказ создан' : 'Выберите регион оплаты'}</h2>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-200 transition hover:border-brand-300/50 hover:bg-brand-500/10"
            >
              x
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto overscroll-contain px-5 py-5 md:px-6 md:py-6">
          {!checkoutOrder ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                {availablePrices.map((price) => {
                  const active = price.region === selectedRegion
                  const cardPriceDisplay = getCheckoutPriceDisplay(price)

                  return (
                    <button
                      key={price.region}
                      type="button"
                      onClick={() => onSelectRegion(price.region)}
                      className={`rounded-[24px] border p-4 text-left transition ${
                        active
                          ? 'border-brand-300/50 bg-[#0f2438] text-white shadow-glow'
                          : 'border-white/10 bg-[#0d1828] text-slate-300 hover:border-brand-300/30'
                      }`}
                    >
                      <div className="text-sm uppercase tracking-[0.24em] text-slate-400">{price.region}</div>
                      <div className="mt-3 flex flex-wrap items-end gap-x-2 gap-y-1">
                        <span className="text-xl font-semibold text-white">{cardPriceDisplay.primary}</span>
                        {cardPriceDisplay.secondary ? (
                          <span className="text-sm font-medium text-slate-400">{cardPriceDisplay.secondary}</span>
                        ) : null}
                      </div>
                      <div className="mt-2 text-sm text-slate-400">{price.name}</div>
                    </button>
                  )
                })}
              </div>

              {canUsePsPlus ? (
                <label className="flex cursor-pointer items-start gap-3 rounded-[22px] border border-white/10 bg-[#0d1828] px-4 py-4">
                  <input
                    type="checkbox"
                    checked={usePsPlus}
                    onChange={(event) => onUsePsPlusChange(event.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-white/10 bg-slate-950/50 text-brand-400"
                  />
                  <span>
                    <span className="block text-sm font-semibold text-white">Использовать цену PS Plus</span>
                    <span className="mt-1 block text-sm leading-7 text-slate-400">
                      Для выбранного региона доступна отдельная цена подписчика.
                    </span>
                  </span>
                </label>
              ) : null}

              <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Данные для покупки</p>
                    <p className="mt-1 text-sm leading-7 text-slate-400">
                      Если чего-то ещё нет в профиле, можно заполнить прямо здесь.
                    </p>
                  </div>
                  {profileLoading ? (
                    <span className="pill bg-white/5 text-slate-300">
                      <LoaderCircle size={14} className="animate-spin" />
                      Профиль загружается
                    </span>
                  ) : null}
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <label className="mb-2 block text-sm font-medium text-slate-200">Email для покупки</label>
                    <input
                      type="email"
                      value={checkoutForm.purchaseEmail}
                      onChange={(event) => onCheckoutFormChange('purchaseEmail', event.target.value)}
                      className={fieldClassName('purchase_email')}
                      placeholder="email@example.com"
                    />
                    {hasSavedPurchaseEmail ? (
                      <p className="mt-2 text-xs text-slate-500">Можно изменить email только для этого заказа.</p>
                    ) : null}
                  </div>

                  {isUkraineCheckout ? (
                    <>
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-200">Платформа</label>
                        <select
                          value={checkoutForm.platform}
                          onChange={(event) =>
                            onCheckoutFormChange(
                              'platform',
                              (event.target.value as CheckoutFormState['platform']) || '',
                            )
                          }
                          className="auth-input"
                        >
                          <option value="">Из профиля / по умолчанию</option>
                          <option value="PS5">PlayStation 5</option>
                          <option value="PS4">PlayStation 4</option>
                        </select>
                      </div>

                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-200">PSN Email</label>
                        <input
                          type="email"
                          value={checkoutForm.psnEmail}
                          onChange={(event) => onCheckoutFormChange('psnEmail', event.target.value)}
                          className={fieldClassName('psn_email')}
                          placeholder="psn@example.com"
                        />
                      </div>

                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-200">PSN Пароль</label>
                        <input
                          type="password"
                          value={checkoutForm.psnPassword}
                          onChange={(event) => onCheckoutFormChange('psnPassword', event.target.value)}
                          className={fieldClassName('psn_password')}
                          placeholder={hasSavedUaPassword ? 'Оставьте пустым, если пароль уже сохранён' : 'Введите PSN пароль'}
                        />
                      </div>

                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-200">Резервный код 2FA</label>
                        <input
                          type="password"
                          value={checkoutForm.backupCode}
                          onChange={(event) => onCheckoutFormChange('backupCode', event.target.value)}
                          className="auth-input"
                          placeholder="Опционально"
                        />
                      </div>
                    </>
                  ) : null}
                </div>
              </div>

              {selectedPrice ? (
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm text-slate-400">Выбранный регион</p>
                      <p className="mt-1 text-lg font-semibold text-white">{selectedPrice.name}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-slate-400">Ориентир по каталогу</p>
                      {selectedPriceDisplay ? (
                        <div className="mt-1">
                          <p className="text-lg font-semibold text-white">{selectedPriceDisplay.primary}</p>
                          {selectedPriceDisplay.secondary ? (
                            <p className="mt-1 text-sm text-slate-500">{selectedPriceDisplay.secondary}</p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {checkoutError ? (
                <div className="auth-alert auth-alert-error">
                  <div className="flex items-start gap-3">
                    <AlertCircle size={18} className="mt-0.5 shrink-0" />
                    <span>{checkoutError}</span>
                  </div>
                </div>
              ) : null}

              {checkoutMessage ? <div className="auth-alert auth-alert-info">{checkoutMessage}</div> : null}

              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <button type="button" className="btn-secondary" onClick={onClose}>
                  Отмена
                </button>
                <button type="button" className="btn-primary" onClick={onCreateOrder} disabled={checkoutLoading || profileLoading}>
                  {checkoutLoading ? <LoaderCircle size={16} className="animate-spin" /> : <CreditCard size={16} />}
                  {checkoutLoading ? 'Подготовка...' : profileLoading ? 'Загружаем профиль...' : 'Получить ссылку на оплату'}
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-[24px] border border-emerald-400/15 bg-emerald-500/10 p-4">
                <div>
                  <p className="text-sm text-emerald-100/80">Номер заказа</p>
                  <p className="mt-1 text-2xl font-semibold text-white">{checkoutOrder.order_number}</p>
                  <p className="mt-2 text-sm leading-7 text-emerald-50/90">
                    Откройте ссылку и завершите оплату на стороне платежки. Покупка уже сохранена в профиле.
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                  <p className="text-sm text-slate-400">Регион</p>
                  <p className="mt-1 text-lg font-semibold text-white">{checkoutOrder.product_region}</p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                  <p className="text-sm text-slate-400">Стоимость</p>
                  {orderPriceDisplay ? (
                    <div className="mt-1">
                      <p className="text-lg font-semibold text-white">{orderPriceDisplay.primary}</p>
                      {orderPriceDisplay.secondary ? (
                        <p className="mt-1 text-sm text-slate-500">{orderPriceDisplay.secondary}</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>

              {paymentMessage ? (
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4 text-sm leading-7 text-slate-200">
                  {paymentMessage}
                </div>
              ) : null}

              {checkoutError ? <div className="auth-alert auth-alert-error">{checkoutError}</div> : null}
              {checkoutMessage ? <div className="auth-alert auth-alert-info">{checkoutMessage}</div> : null}

              <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap">
                <button type="button" className="btn-primary" onClick={onOpenPayment}>
                  <ExternalLink size={16} />
                  Перейти к оплате
                </button>
                <button type="button" className="btn-secondary" onClick={onCopyPaymentLink}>
                  <Copy size={16} />
                  Скопировать ссылку
                </button>
              </div>

              {checkoutOrder.payment_url ? (
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                  <p className="text-sm text-slate-400">Ссылка на оплату</p>
                  <p className="mt-2 break-all text-sm leading-7 text-white">{checkoutOrder.payment_url}</p>
                </div>
              ) : null}

              <div className="rounded-[24px] border border-white/10 bg-[#0b1522] p-4 text-sm leading-7 text-slate-300">
                Оплатите по этой ссылке, а после оплаты отправьте нужный код прямо в чате оплаты. Ссылка и дата покупки уже
                сохранены в профиле.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export function ProductPage() {
  const { productId } = useParams<{ productId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const requestedRegion = searchParams.get('region') || undefined

  const { user, isAuthenticated } = useAuth()
  const { isFavorite, toggleFavorite } = useFavorites()

  const [product, setProduct] = useState<CatalogProduct | null>(null)
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState<SourceMode>('api')
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)
  const [checkoutRegion, setCheckoutRegion] = useState('TR')
  const [usePsPlusCheckout, setUsePsPlusCheckout] = useState(false)
  const [checkoutOrder, setCheckoutOrder] = useState<PurchaseOrder | null>(null)
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [checkoutProfile, setCheckoutProfile] = useState<SiteProfileResponse | null>(null)
  const [checkoutProfileLoading, setCheckoutProfileLoading] = useState(false)
  const [checkoutForm, setCheckoutForm] = useState<CheckoutFormState>(EMPTY_CHECKOUT_FORM)
  const [checkoutMissingFields, setCheckoutMissingFields] = useState<CheckoutFieldName[]>([])
  const [checkoutMessage, setCheckoutMessage] = useState<string | null>(null)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    if (!productId) {
      setLoading(false)
      return
    }

    ;(async () => {
      try {
        const response = await fetchProduct(productId, requestedRegion)
        if (!ignore) {
          setProduct(response)
          setSource('api')
        }
      } catch {
        if (!ignore) {
          const fallback =
            mockProducts.find((item) => item.id === productId) ||
            mockProducts.find((item) => item.routeRegion === requestedRegion) ||
            mockProducts[0]

          setProduct(fallback)
          setSource('mock')
        }
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [productId, requestedRegion])

  const coverUrl = normalizeImageUrl(product?.image)
  const region = resolveRegionPresentation(product?.routeRegion || product?.region, product?.regionInfo?.name)
  const highlights = useMemo(() => (product ? buildHighlights(product) : []), [product])
  const regionalPrices = useMemo(() => (product ? getVisibleRegionalPrices(product).slice(0, 3) : []), [product])
  const favoriteActive = product ? isFavorite(product.id) : false
  const productTitle = product ? getProductTitle(product) : 'РўРѕРІР°СЂЂ'
  const availableCheckoutRegions = useMemo(() => regionalPrices.map((price) => price.region), [regionalPrices])
  const selectedRegionPrice = useMemo(
    () => regionalPrices.find((item) => item.region === checkoutRegion) ?? regionalPrices[0] ?? null,
    [checkoutRegion, regionalPrices],
  )
  const canUsePsPlus = Boolean(selectedRegionPrice?.psPlusPriceRub && selectedRegionPrice.psPlusPriceRub > 0)

  useEffect(() => {
    if (availableCheckoutRegions.length === 0) {
      return
    }

    setCheckoutRegion((current) => {
      if (availableCheckoutRegions.includes(current)) {
        return current
      }

      return getPreferredCheckoutRegion(availableCheckoutRegions, requestedRegion, user?.preferred_region)
    })
  }, [availableCheckoutRegions, requestedRegion, user?.preferred_region])

  useEffect(() => {
    if (!canUsePsPlus && usePsPlusCheckout) {
      setUsePsPlusCheckout(false)
    }
  }, [canUsePsPlus, usePsPlusCheckout])

  function handleFavoriteClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    if (product) {
      toggleFavorite({
        productId: product.id,
        region: product.routeRegion || product.region,
      })
    }
  }

  function handleCheckoutFormChange<K extends keyof CheckoutFormState>(field: K, value: CheckoutFormState[K]) {
    setCheckoutForm((current) => ({
      ...current,
      [field]: value,
    }))

    const fieldNameMap: Partial<Record<keyof CheckoutFormState, CheckoutFieldName>> = {
      purchaseEmail: 'purchase_email',
      psnEmail: 'psn_email',
      psnPassword: 'psn_password',
    }
    const mappedField = fieldNameMap[field]
    if (mappedField) {
      setCheckoutMissingFields((current) => current.filter((item) => item !== mappedField))
    }
  }

  async function openCheckout() {
    if (!product) {
      return
    }

    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    setCheckoutOrder(null)
    setCheckoutMessage(null)
    setCheckoutError(null)
    setCheckoutMissingFields([])
    setCheckoutForm(
      buildCheckoutForm(checkoutProfile, {
        payment_email: user?.payment_email,
        platform: user?.platform,
        psn_email: user?.psn_email,
      }),
    )
    setIsCheckoutOpen(true)

    setCheckoutProfileLoading(true)
    try {
      const profileResponse = await getProfile()
      setCheckoutProfile(profileResponse)
      setCheckoutForm(
        buildCheckoutForm(profileResponse, {
          payment_email: user?.payment_email,
          platform: user?.platform,
          psn_email: user?.psn_email,
        }),
      )
    } catch {
      setCheckoutProfile(null)
    } finally {
      setCheckoutProfileLoading(false)
    }
  }

  async function handleCreateCheckout() {
    if (!product) {
      return
    }

    const localMissingFields = getMissingCheckoutFields(checkoutRegion, checkoutForm, checkoutProfile)
    if (localMissingFields.length) {
      setCheckoutMissingFields(localMissingFields)
      setCheckoutError('Заполните отмеченные поля для продолжения покупки.')
      setCheckoutMessage(null)
      return
    }

    setCheckoutLoading(true)
    setCheckoutMessage(null)
    setCheckoutError(null)
    setCheckoutMissingFields([])

    try {
      const order = await createPurchaseCheckout({
        product_id: product.id,
        region: checkoutRegion,
        use_ps_plus: usePsPlusCheckout && canUsePsPlus,
        purchase_email: checkoutForm.purchaseEmail.trim() || undefined,
        platform: checkoutRegion === 'UA' ? checkoutForm.platform || undefined : undefined,
        psn_email: checkoutRegion === 'UA' ? checkoutForm.psnEmail.trim() || undefined : undefined,
        psn_password: checkoutRegion === 'UA' ? checkoutForm.psnPassword.trim() || undefined : undefined,
        backup_code: checkoutRegion === 'UA' ? checkoutForm.backupCode.trim() || undefined : undefined,
      })
      setCheckoutOrder(order)
      setCheckoutMessage('Заказ создан. Ссылка на оплату сохранена и будет доступна в профиле.')
    } catch (error) {
      const detail = getApiErrorDetail(error)
      if (detail && typeof detail !== 'string' && Array.isArray(detail.missing_fields)) {
        const missingFields = detail.missing_fields.filter(
          (field): field is CheckoutFieldName =>
            field === 'purchase_email' || field === 'psn_email' || field === 'psn_password',
        )
        setCheckoutMissingFields(missingFields)
        setCheckoutError('Заполните отмеченные поля для продолжения покупки.')
      } else {
        setCheckoutError(getApiErrorMessage(error, 'Не удалось подготовить ссылку на оплату.'))
      }
    } finally {
      setCheckoutLoading(false)
    }
  }

  function handleOpenPayment() {
    if (!checkoutOrder?.payment_url) {
      return
    }

    window.open(checkoutOrder.payment_url, '_blank', 'noopener,noreferrer')
  }

  async function handleCopyPaymentLink() {
    if (!checkoutOrder?.payment_url) {
      return
    }

    try {
      await navigator.clipboard.writeText(checkoutOrder.payment_url)
      setCheckoutMessage('Ссылка на оплату скопирована.')
    } catch {
      setCheckoutError('Не удалось скопировать ссылку автоматически.')
    }
  }

  if (!productId) {
    return (
      <div className="container py-12">
        <div className="panel-soft rounded-[28px] px-6 py-12 text-center text-slate-300">Товар не найден.</div>
      </div>
    )
  }

  return (
    <div className="container py-10 md:py-14">
      <div className="mb-6">
        <Link
          to="/catalog"
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm text-white transition hover:border-brand-300/60 hover:bg-brand-500/10"
        >
          <ArrowLeft size={16} />
          Назад в каталог
        </Link>
      </div>

      {loading ? (
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="aspect-[16/10] animate-pulse rounded-[32px] bg-white/10" />
          <div className="space-y-4">
            <div className="h-10 animate-pulse rounded-2xl bg-white/10" />
            <div className="h-48 animate-pulse rounded-[28px] bg-white/10" />
            <div className="h-36 animate-pulse rounded-[28px] bg-white/10" />
          </div>
        </div>
      ) : product ? (
        <div className="space-y-10">
          <section className="grid gap-8 lg:grid-cols-[1.04fr_0.96fr] lg:items-start">
            <div className="panel overflow-hidden">
              <div className="relative">
                {coverUrl ? (
                  <img src={coverUrl} alt={productTitle} className="aspect-[16/10] w-full object-cover" />
                ) : (
                  <div className="mesh-bg flex aspect-[16/10] items-center justify-center">
                    <div className="text-center">
                      <Gamepad2 className="mx-auto h-14 w-14 text-brand-200/70" />
                      <p className="mt-4 text-lg font-semibold text-white">{productTitle}</p>
                    </div>
                  </div>
                )}

                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/15 to-transparent" />

                <div className="absolute left-5 top-5 flex flex-wrap gap-2">
                  <span className="pill bg-slate-950/70 text-brand-50">{region.label}</span>
                  {product.hasDiscount ? (
                    <span className="pill border-rose-400/20 bg-rose-500/20 text-rose-100">
                      <BadgePercent size={12} />
                      {product.discountPercent ? `-${product.discountPercent}%` : 'Скидка'}
                    </span>
                  ) : null}
                  {product.hasPsPlus ? (
                    <span className="pill border-amber-300/20 bg-amber-400/20 text-amber-50">PS Plus</span>
                  ) : null}
                </div>

                <FavoriteButton
                  active={favoriteActive}
                  onClick={handleFavoriteClick}
                  variant="hero"
                  className="absolute right-5 top-5 z-10"
                />

                {product.rating ? (
                  <div className="absolute bottom-5 right-5 flex items-center gap-1 rounded-full border border-white/10 bg-slate-950/75 px-4 py-2 text-white shadow-lg">
                    <Star size={15} className="fill-amber-300 text-amber-300" />
                    {formatRating(product.rating)}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="space-y-6">
              <div className="space-y-4">
                <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">
                  {product.category || 'Каталог'} • {source === 'api' ? 'live API' : 'demo preview'}
                </p>
                <h1 className="text-4xl text-white md:text-5xl">{productTitle}</h1>

                <div className="flex flex-wrap gap-2">
                  {product.platforms ? (
                    <span className="pill border-white/10 bg-white/5 text-slate-200">{product.platforms}</span>
                  ) : null}
                  <LocalizationBadge localizationName={product.localizationName} />
                  {product.hasEaAccess ? (
                    <span className="pill border-sky-300/20 bg-sky-500/15 text-sky-50">EA Access</span>
                  ) : null}
                </div>
              </div>

              <div className="panel-soft rounded-[28px] p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                  </div>

                  <button type="button" className="btn-primary shrink-0" onClick={openCheckout}>
                    <CreditCard size={16} />
                    {isAuthenticated ? 'Купить' : 'Войти и купить'}
                  </button>
                </div>

                <RegionalPriceList prices={regionalPrices} variant="detail" className="mt-6" />
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                {highlights.map(({ label, value, icon: Icon }) => (
                  <div key={label} className="rounded-[22px] border border-white/10 bg-white/5 p-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-200">
                      <Icon size={18} />
                    </div>
                    <p className="mt-4 text-xs uppercase tracking-[0.24em] text-slate-500">{label}</p>
                    <p className="mt-2 text-sm font-semibold text-white">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="panel-soft rounded-[28px] p-6">
              <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">Описание</p>
              <p className="mt-4 whitespace-pre-line text-base leading-8 text-slate-300">
                {product.description || 'Описание товара пока недоступно.'}
              </p>
            </div>

            <div className="space-y-6">
              <div className="panel-soft rounded-[28px] p-6">
                <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">Теги</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(product.tags.length ? product.tags : ['PlayStation', 'Store', 'Каталог']).map((tag) => (
                    <span key={tag} className="pill bg-white/5 text-slate-200">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="panel-soft rounded-[28px] p-6">
                <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">Комплект</p>
                <ul className="mt-4 space-y-3 text-sm text-slate-300">
                  {(product.compound.length
                    ? product.compound
                    : ['Состав издания и бонусов появится здесь, как только API отдаст подробности.']).map((item) => (
                    <li key={item} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        </div>
      ) : (
        <div className="panel-soft rounded-[28px] px-6 py-12 text-center text-slate-300">Товар не найден.</div>
      )}

      <CheckoutDialog
        open={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        selectedRegion={checkoutRegion}
        onSelectRegion={(regionValue) => {
          setCheckoutRegion(regionValue)
          setCheckoutOrder(null)
          setCheckoutMessage(null)
          setCheckoutError(null)
          setCheckoutMissingFields([])
        }}
        availablePrices={regionalPrices}
        usePsPlus={usePsPlusCheckout}
        onUsePsPlusChange={(value) => {
          setUsePsPlusCheckout(value)
          setCheckoutOrder(null)
          setCheckoutMessage(null)
          setCheckoutError(null)
          setCheckoutMissingFields([])
        }}
        canUsePsPlus={canUsePsPlus}
        checkoutOrder={checkoutOrder}
        checkoutLoading={checkoutLoading}
        profileLoading={checkoutProfileLoading}
        checkoutForm={checkoutForm}
        onCheckoutFormChange={handleCheckoutFormChange}
        missingFields={checkoutMissingFields}
        hasSavedPurchaseEmail={Boolean(checkoutProfile?.user.payment_email)}
        hasSavedUaPassword={Boolean(checkoutProfile?.psn_accounts?.UA?.has_password)}
        checkoutMessage={checkoutMessage}
        checkoutError={checkoutError}
        onCreateOrder={handleCreateCheckout}
        onOpenPayment={handleOpenPayment}
        onCopyPaymentLink={handleCopyPaymentLink}
      />
    </div>
  )
}
