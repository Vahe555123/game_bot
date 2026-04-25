import {
  AlertCircle,
  ArrowLeft,
  BadgePercent,
  CreditCard,
  ExternalLink,
  Gamepad2,
  LoaderCircle,
  Star,
} from 'lucide-react'
import { useEffect, useMemo, useState, type MouseEvent } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { buildAuthModalPath, buildBaseAuthPath } from '../components/auth/authModalState'
import { FavoriteButton } from '../components/catalog/FavoriteButton'
import { PsPlusSavingsBadge } from '../components/catalog/PsPlusSavingsBadge'
import { RegionalPriceList } from '../components/catalog/RegionalPriceList'
import { PasswordInput } from '../components/forms/PasswordInput'
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
import { getLocalPlayersRangeFromInfo } from '../utils/catalogFilters'
import {
  formatDualCurrencyInline,
  formatRating,
  getDualCurrencyPriceDisplay,
  normalizeImageUrl,
  resolveRegionPresentation,
} from '../utils/format'
import {
  getProductPsPlusSavingsPercent,
  getProductRegularDiscountPercent,
  getProductTitle,
  getVisibleRegionalPrices,
} from '../utils/productPresentation'

type CheckoutFieldName = 'purchase_email' | 'psn_email' | 'psn_password'

type CheckoutFormState = {
  purchaseEmail: string
  psnEmail: string
  psnPassword: string
  backupCode: string
}

type CheckoutPaymentSummary = {
  kind: 'default' | 'card' | 'ukraine'
  currencyCode: string | null
  priceLocal: number | null
  priceRub: number | null
  gamePrice: number | null
  payableAmount: number | null
  remainingBalance: number | null
  message: string | null
  directCardUrl: string | null
}

const EMPTY_CHECKOUT_FORM: CheckoutFormState = {
  purchaseEmail: '',
  psnEmail: '',
  psnPassword: '',
  backupCode: '',
}

function buildCheckoutForm(
  profile: SiteProfileResponse | null,
  fallbackUser?: { payment_email?: string | null; psn_email?: string | null } | null,
): CheckoutFormState {
  const uaAccount = profile?.psn_accounts?.UA

  return {
    purchaseEmail: profile?.user.payment_email ?? fallbackUser?.payment_email ?? '',
    psnEmail: uaAccount?.psn_email ?? fallbackUser?.psn_email ?? '',
    psnPassword: uaAccount?.psn_password ?? '',
    backupCode: '',
  }
}

function formatDiscountEndDate(value?: string | null) {
  const source = value?.trim()
  if (!source) {
    return null
  }

  const isoDateMatch = source.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (isoDateMatch) {
    const [, year, month, day] = isoDateMatch
    return `${day}.${month}.${year}`
  }

  const parsedDate = new Date(source)
  if (Number.isNaN(parsedDate.getTime())) {
    return null
  }

  return parsedDate.toLocaleDateString('ru-RU')
}

function formatReleaseDate(value?: string | null) {
  return formatDiscountEndDate(value)
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

function resolvePlayersLabel(product: CatalogProduct) {
  const minPlayers = typeof product.playersMin === 'number' ? product.playersMin : null
  const maxPlayers = typeof product.playersMax === 'number' ? product.playersMax : null

  if (minPlayers !== null && maxPlayers !== null) {
    return minPlayers === maxPlayers ? `${minPlayers}` : `${minPlayers} - ${maxPlayers}`
  }

  if (minPlayers !== null) {
    return `${minPlayers}`
  }

  const localPlayersRange = getLocalPlayersRangeFromInfo(product.info)
  if (localPlayersRange) {
    return localPlayersRange.min === localPlayersRange.max
      ? `${localPlayersRange.min}`
      : `${localPlayersRange.min} - ${localPlayersRange.max}`
  }

  const infoPlayers = product.info.find((item) => /^\s*Игроки\s*:/i.test(item) && !/в\s+сети|PS\s*Plus/i.test(item))
  if (!infoPlayers) {
    return null
  }

  return infoPlayers.replace(/^\s*Игроки\s*:\s*/i, '').trim() || infoPlayers.trim()
}

function buildInfoItems(product: CatalogProduct, playersLabel: string | null) {
  const region = resolveRegionPresentation(product.region, product.regionInfo?.name)
  const infoItems = product.info.filter((item) => Boolean(item) && !/игрок/i.test(item) && !/жанр/i.test(item))
  const releaseDate = formatReleaseDate(product.releaseDate)

  return [
    `Есть в PS Plus: ${product.hasPsPlus ? 'Да' : 'Нет'}`,
    `Есть в EA Play: ${product.hasEaAccess ? 'Да' : 'Нет'}`,
    `Дата выхода: ${releaseDate || 'Не указана'}`,
    product.publisher ? `Издатель: ${product.publisher}` : null,
    product.platforms ? `Платформы: ${product.platforms}` : null,
    region.name ? `Регион: ${region.name}` : null,
    playersLabel ? `Игроки: ${playersLabel}` : null,
    product.category ? `Жанр: ${product.category}` : null,
    ...infoItems,
  ].filter((item): item is string => Boolean(item))
}

function getCheckoutPriceDisplay(price: ProductRegionPrice, usePsPlus = false) {
  const localValue = usePsPlus && price.psPlusPriceLocal !== null ? price.psPlusPriceLocal : price.priceLocal
  const rubValue = usePsPlus && price.psPlusPriceRub !== null ? price.psPlusPriceRub : price.priceRub

  return getDualCurrencyPriceDisplay(localValue, price.currencyCode, rubValue)
}

function isPaymentMetadataRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getPaymentMetadataNumber(record: Record<string, unknown>, key: string) {
  const value = record[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function getPaymentMetadataString(record: Record<string, unknown>, key: string) {
  const value = record[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function buildCheckoutPaymentSummary(order: PurchaseOrder | null): CheckoutPaymentSummary | null {
  if (!order) {
    return null
  }

  const metadata = order.payment_metadata || {}
  const cardInfo = metadata.card_info
  if (isPaymentMetadataRecord(cardInfo)) {
    return {
      kind: 'card',
      currencyCode: order.currency_code,
      priceLocal: getPaymentMetadataNumber(cardInfo, 'total_value') ?? order.local_price,
      priceRub: getPaymentMetadataNumber(cardInfo, 'card_price_rub') ?? order.price_rub,
      gamePrice: getPaymentMetadataNumber(cardInfo, 'game_price'),
      payableAmount: getPaymentMetadataNumber(cardInfo, 'total_value') ?? order.local_price,
      remainingBalance: getPaymentMetadataNumber(cardInfo, 'remaining_balance'),
      message: getPaymentMetadataString(cardInfo, 'message_ru'),
      directCardUrl: getPaymentMetadataString(cardInfo, 'direct_card_url'),
    }
  }

  const topupInfo = metadata.topup_info
  if (isPaymentMetadataRecord(topupInfo)) {
    return {
      kind: 'ukraine',
      currencyCode: order.currency_code,
      priceLocal: getPaymentMetadataNumber(topupInfo, 'topup_amount') ?? order.local_price,
      priceRub: getPaymentMetadataNumber(topupInfo, 'card_price_rub') ?? order.price_rub,
      gamePrice: getPaymentMetadataNumber(topupInfo, 'game_price'),
      payableAmount: getPaymentMetadataNumber(topupInfo, 'topup_amount') ?? order.local_price,
      remainingBalance: getPaymentMetadataNumber(topupInfo, 'remaining_balance'),
      message: getPaymentMetadataString(topupInfo, 'message_ru'),
      directCardUrl: getPaymentMetadataString(topupInfo, 'direct_card_url'),
    }
  }

  return {
    kind: 'default',
    currencyCode: order.currency_code,
    priceLocal: order.local_price,
    priceRub: order.price_rub,
    gamePrice: null,
    payableAmount: order.local_price,
    remainingBalance: null,
    message: null,
    directCardUrl: null,
  }
}

function isValidEmailAddress(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
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
  const paymentSummary = buildCheckoutPaymentSummary(checkoutOrder)
  const paymentMessage = paymentSummary?.message
  const isUkraineCheckout = selectedRegion === 'UA'
  const selectedPriceDisplay = selectedPrice ? getCheckoutPriceDisplay(selectedPrice, usePsPlus) : null
  const orderPriceDisplay = paymentSummary
    ? getDualCurrencyPriceDisplay(paymentSummary.priceLocal, paymentSummary.currencyCode, paymentSummary.priceRub)
    : null
  const orderPriceLabel =
    paymentSummary?.kind === 'card' ? 'Стоимость карты' : paymentSummary?.kind === 'ukraine' ? 'Сумма к оплате' : 'Стоимость'
  const paymentGamePrice = paymentSummary?.gamePrice ?? null
  const paymentRemainingBalance = paymentSummary?.remainingBalance ?? null
  const paymentPayableAmount = paymentSummary?.payableAmount ?? null
  const paymentCurrencyCode = paymentSummary?.currencyCode ?? checkoutOrder?.currency_code ?? null
  const paymentDirectCardUrl = paymentSummary?.directCardUrl ?? null
  const hasGamePrice = paymentGamePrice !== null
  const psPlusSavingsPercent = selectedPrice?.psPlusDiscountPercent ?? null
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
                    <span className="block text-sm font-semibold text-white">У Вас есть активная подписка PS Plus на этом аккаунте?</span>
                    <span className="mt-1 block text-sm leading-7 text-slate-400">
                      {psPlusSavingsPercent
                        ? `Сэкономьте ${psPlusSavingsPercent} процентов с Playstation Plus.`
                        : 'Для выбранного региона доступна отдельная цена подписчика.'}
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
                      <p className="mt-2 text-xs text-slate-500">Если изменить email и продолжить, он обновится и в профиле.</p>
                    ) : null}
                  </div>

                  {isUkraineCheckout ? (
                    <>
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
                        <PasswordInput
                          value={checkoutForm.psnPassword}
                          onChange={(value) => onCheckoutFormChange('psnPassword', value)}
                          className={fieldClassName('psn_password')}
                          placeholder={hasSavedUaPassword ? 'Сохранённый PSN пароль' : 'Введите PSN пароль'}
                          autoComplete="current-password"
                        />
                      </div>

                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-200">Резервный код 2FA</label>
                        <PasswordInput
                          value={checkoutForm.backupCode}
                          onChange={(value) => onCheckoutFormChange('backupCode', value)}
                          className="auth-input"
                          placeholder="Введите код для этой покупки"
                          autoComplete="one-time-code"
                        />
                      </div>

                      <div className="md:col-span-2 rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm leading-7 text-slate-400">
                        Email для покупки, PSN email и пароль сохранятся в профиле после продолжения покупки.
                        Резервный код используется только для текущего заказа и не сохраняется.
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
                  {checkoutLoading ? 'Подготовка...' : profileLoading ? 'Загружаем профиль...' : 'Продолжить'}
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
                    Откройте страницу оплаты и завершите покупку. Данные для заказа уже сохранены в профиле.
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                  <p className="text-sm text-slate-400">Регион</p>
                  <p className="mt-1 text-lg font-semibold text-white">{checkoutOrder.product_region}</p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                  <p className="text-sm text-slate-400">{orderPriceLabel}</p>
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

              {hasGamePrice ? (
                <div
                  className={`grid gap-4 ${
                    typeof paymentRemainingBalance === 'number' && paymentRemainingBalance > 0 ? 'md:grid-cols-2' : ''
                  }`}
                >
                  <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                    <p className="text-sm text-slate-400">Цена игры</p>
                    <p className="mt-1 text-lg font-semibold text-white">
                      {formatDualCurrencyInline(paymentGamePrice, paymentCurrencyCode, null)}
                    </p>
                  </div>
                  {typeof paymentRemainingBalance === 'number' && paymentRemainingBalance > 0 ? (
                    <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4">
                      <p className="text-sm text-slate-400">Останется в кошельке</p>
                      <p className="mt-1 text-lg font-semibold text-white">
                        {formatDualCurrencyInline(paymentRemainingBalance, paymentCurrencyCode, null)}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {paymentSummary?.kind !== 'ukraine' && paymentMessage ? (
                <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4 text-sm leading-7 text-slate-200">
                  <p>{paymentMessage}</p>
                  {paymentDirectCardUrl ? (
                    <p className="mt-3 text-slate-300">
                      Либо карту на нужную сумму можно купить{' '}
                      <a href={paymentDirectCardUrl} className="font-semibold text-brand-200 underline underline-offset-4">
                        отдельно
                      </a>
                      .
                    </p>
                  ) : null}
                </div>
              ) : null}

              {paymentSummary?.kind === 'ukraine' ? (
                <>
                  {paymentDirectCardUrl && typeof paymentRemainingBalance === 'number' && paymentRemainingBalance > 0 ? (
                    <div className="rounded-[24px] border border-white/10 bg-[#0d1828] p-4 text-sm leading-7 text-slate-200">
                      Игра стоит меньше минимальной суммы пополнения, поэтому к оплате будет{' '}
                      {formatDualCurrencyInline(paymentPayableAmount, paymentCurrencyCode, null)}. Либо пополнение
                      на эту сумму можно купить{' '}
                      <a href={paymentDirectCardUrl} className="font-semibold text-brand-200 underline underline-offset-4">
                        отдельно
                      </a>
                      .
                    </div>
                  ) : null}

                  <div className="rounded-[24px] border border-white/10 bg-[#0b1522] p-4 text-sm leading-7 text-slate-300">
                    <p>
                      После оплаты Вы попадете на страницу, где сверху будет указан "уникальный код", скопируйте его. Затем
                      опуститесь в самый низ этой страницы до "Чата переписки с продавцом", вставьте туда скопированный уникальный
                      код и отправьте.
                    </p>
                    <p className="mt-3">
                      Подробнее можно посмотреть в этом видеогайде{' '}
                      <a
                        href="https://youtu.be/-ApyE29u69I"
                        target="_blank"
                        rel="noreferrer"
                        className="font-semibold text-brand-200 underline underline-offset-4"
                      >
                        с 6:04
                      </a>{' '}
                      или{' '}
                      <a
                        href="https://vkvideo.ru/video-85844500_456240978?list=ln-qW4ZU3syiRhSZ1IKe5"
                        target="_blank"
                        rel="noreferrer"
                        className="font-semibold text-brand-200 underline underline-offset-4"
                      >
                        здесь
                      </a>
                      .
                    </p>
                    <p className="mt-3">
                      После того, как отправите его, в порядке очереди поступления заказов (обычно от 15 минут до часа) с Вами
                      свяжется там продавец, выполнит заказ и Вам на почту придет уведомление. Время работы менеджера с 11 до 21 по
                      МСК. Если заказ был сделан в нерабочее время, то на выполнение может потребоваться больше времени, так как
                      могла скопиться очередь из заказов.
                    </p>
                  </div>
                </>
              ) : null}

              {checkoutError ? <div className="auth-alert auth-alert-error">{checkoutError}</div> : null}
              {checkoutMessage ? <div className="auth-alert auth-alert-info">{checkoutMessage}</div> : null}

              <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap">
                <button type="button" className="btn-primary" onClick={onOpenPayment}>
                  <ExternalLink size={16} />
                  Перейти к оплате
                </button>
                {paymentDirectCardUrl ? (
                  <a href={paymentDirectCardUrl} className="btn-secondary">
                    <CreditCard size={16} />
                    {paymentSummary?.kind === 'ukraine' ? 'Купить пополнение отдельно' : 'Купить карту отдельно'}
                  </a>
                ) : null}
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
  const location = useLocation()
  const navigate = useNavigate()
  const requestedRegion = searchParams.get('region') || undefined
  const rawCatalogPath =
    typeof (location.state as { catalogPath?: string } | null)?.catalogPath === 'string'
      ? (location.state as { catalogPath?: string }).catalogPath
      : null
  const catalogPath =
    rawCatalogPath && (rawCatalogPath === '/' || rawCatalogPath.startsWith('/?') || rawCatalogPath.startsWith('/catalog'))
      ? rawCatalogPath
      : null

  const { user, isAuthenticated, refreshUser } = useAuth()
  const { isFavorite, toggleFavorite } = useFavorites()

  const [product, setProduct] = useState<CatalogProduct | null>(null)
  const [loading, setLoading] = useState(true)
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

  function applyCheckoutProfile(profileResponse: SiteProfileResponse | null) {
    setCheckoutProfile(profileResponse)
    setCheckoutForm(
      buildCheckoutForm(profileResponse, {
        payment_email: user?.payment_email,
        psn_email: user?.psn_email,
      }),
    )
  }

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
        }
      } catch {
        if (!ignore) {
          const fallback =
            mockProducts.find((item) => item.id === productId) ||
            mockProducts.find((item) => item.region === requestedRegion) ||
            mockProducts[0]

          setProduct(fallback)
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
  const regionalPrices = useMemo(() => (product ? getVisibleRegionalPrices(product).slice(0, 3) : []), [product])
  const favoriteActive = product ? isFavorite(product.id) : false
  const productTitle = product ? getProductTitle(product) : 'Товар'
  const psPlusSavingsPercent = product ? getProductPsPlusSavingsPercent(product) : null
  const regularDiscountPercent = product ? getProductRegularDiscountPercent(product) : null
  const playersLabel = useMemo(() => (product ? resolvePlayersLabel(product) : null), [product])
  const infoItems = useMemo(() => (product ? buildInfoItems(product, playersLabel) : []), [product, playersLabel])
  const checkoutPrices = useMemo(
    () =>
      regionalPrices.filter(
        (price) =>
          price.available &&
          ((typeof price.priceRub === 'number' && price.priceRub > 0) ||
            (typeof price.priceLocal === 'number' && price.priceLocal > 0)),
      ),
    [regionalPrices],
  )
  const availableCheckoutRegions = useMemo(() => checkoutPrices.map((price) => price.region), [checkoutPrices])
  const selectedRegionPrice = useMemo(
    () => checkoutPrices.find((item) => item.region === checkoutRegion) ?? checkoutPrices[0] ?? null,
    [checkoutRegion, checkoutPrices],
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
        region: product.region,
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
    if (!checkoutPrices.length) {
      return
    }

    if (!isAuthenticated) {
      navigate(buildAuthModalPath(location, 'login', buildBaseAuthPath(location)))
      return
    }

    setCheckoutOrder(null)
    setCheckoutMessage(null)
    setCheckoutError(null)
    setCheckoutMissingFields([])
    applyCheckoutProfile(checkoutProfile)
    setIsCheckoutOpen(true)

    setCheckoutProfileLoading(true)
    try {
      const profileResponse = await getProfile()
      applyCheckoutProfile(profileResponse)
    } catch {
      applyCheckoutProfile(null)
    } finally {
      setCheckoutProfileLoading(false)
    }
  }

  async function handleCreateCheckout() {
    if (!product) {
      return
    }

    const purchaseEmail = checkoutForm.purchaseEmail.trim()
    const psnEmail = checkoutForm.psnEmail.trim()
    const localMissingFields = getMissingCheckoutFields(checkoutRegion, checkoutForm, checkoutProfile)
    if (localMissingFields.length) {
      setCheckoutMissingFields(localMissingFields)
      setCheckoutError('Заполните отмеченные поля для продолжения покупки.')
      setCheckoutMessage(null)
      return
    }

    const invalidFields: CheckoutFieldName[] = []
    if (purchaseEmail && !isValidEmailAddress(purchaseEmail)) {
      invalidFields.push('purchase_email')
    }
    if (checkoutRegion === 'UA' && psnEmail && !isValidEmailAddress(psnEmail)) {
      invalidFields.push('psn_email')
    }
    if (invalidFields.length) {
      setCheckoutMissingFields(invalidFields)
      setCheckoutError(
        invalidFields.includes('purchase_email') && invalidFields.includes('psn_email')
          ? 'Проверьте корректность email в отмеченных полях.'
          : invalidFields.includes('purchase_email')
            ? 'Введите корректный Email для покупок.'
            : 'Введите корректный PSN Email.',
      )
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
        purchase_email: purchaseEmail || undefined,
        psn_email: checkoutRegion === 'UA' ? psnEmail || undefined : undefined,
        psn_password: checkoutRegion === 'UA' ? checkoutForm.psnPassword.trim() || undefined : undefined,
        backup_code: checkoutRegion === 'UA' ? checkoutForm.backupCode.trim() || undefined : undefined,
      })
      setCheckoutOrder(order)
      setCheckoutMessage('Заказ создан. Данные для покупки сохранены в профиле.')

      const [profileResponse] = await Promise.all([
        getProfile().catch(() => null),
        refreshUser().catch(() => null),
      ])
      if (profileResponse) {
        applyCheckoutProfile(profileResponse)
      }
    } catch (error) {
      const detail = getApiErrorDetail(error)
      if (detail && !Array.isArray(detail) && typeof detail !== 'string' && Array.isArray(detail.missing_fields)) {
        const missingFields = detail.missing_fields.filter(
          (field): field is CheckoutFieldName =>
            field === 'purchase_email' || field === 'psn_email' || field === 'psn_password',
        )
        setCheckoutMissingFields(missingFields)
        setCheckoutError('Заполните отмеченные поля для продолжения покупки.')
      } else if (Array.isArray(detail)) {
        const invalidEmailField = detail.find(
          (item) =>
            item &&
            typeof item === 'object' &&
            'loc' in item &&
            Array.isArray(item.loc) &&
            (item.loc.includes('purchase_email') || item.loc.includes('psn_email')),
        )
        if (invalidEmailField && Array.isArray(invalidEmailField.loc)) {
          const invalidFieldNames = invalidEmailField.loc.filter(
            (field): field is CheckoutFieldName =>
              field === 'purchase_email' || field === 'psn_email' || field === 'psn_password',
          )
          setCheckoutMissingFields(invalidFieldNames)
          setCheckoutError(
            invalidFieldNames.includes('purchase_email') ? 'Введите корректный Email для покупок.' : 'Введите корректный PSN Email.',
          )
        } else {
          setCheckoutError(getApiErrorMessage(error, 'Не удалось подготовить ссылку на оплату.'))
        }
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

    window.location.assign(checkoutOrder.payment_url)
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
      {catalogPath ? (
        <div className="mb-6">
          <Link
            to={catalogPath}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm text-white transition hover:border-brand-300/60 hover:bg-brand-500/10"
          >
            <ArrowLeft size={16} />
            Назад в каталог
          </Link>
        </div>
      ) : null}

      {loading ? (
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="aspect-square animate-pulse rounded-[32px] bg-white/10" />
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
                  <img src={coverUrl} alt={productTitle} className="aspect-square w-full object-cover" />
                ) : (
                  <div className="mesh-bg flex aspect-square items-center justify-center">
                    <div className="text-center">
                      <Gamepad2 className="mx-auto h-14 w-14 text-brand-200/70" />
                      <p className="mt-4 text-lg font-semibold text-white">{productTitle}</p>
                    </div>
                  </div>
                )}

                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/15 to-transparent" />

                <div className="absolute left-5 right-20 top-5 flex flex-wrap gap-2">
                  {regularDiscountPercent ? (
                    <span className="pill border-rose-400/40 bg-rose-500 px-3 py-1.5 text-[11px] text-white shadow-lg shadow-rose-950/30">
                      <BadgePercent size={12} />
                      -{regularDiscountPercent}%
                    </span>
                  ) : null}
                  {psPlusSavingsPercent ? (
                    <PsPlusSavingsBadge percent={psPlusSavingsPercent} className="px-3 py-1.5 text-[13px]" />
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
                <h1 className="text-4xl text-white md:text-5xl">{productTitle}</h1>

                <div className="flex flex-wrap gap-2">
                  {product.platforms ? (
                    <span className="pill border-white/10 bg-white/5 text-slate-200">{product.platforms}</span>
                  ) : null}
                  {playersLabel ? (
                    <span className="pill border-white/10 bg-white/5 text-slate-200">Игроки: {playersLabel}</span>
                  ) : null}
                  {product.hasEaAccess ? (
                    <span className="pill border-sky-300/20 bg-sky-500/15 text-sky-50">EA Access</span>
                  ) : null}
                </div>
              </div>

              <div className="panel-soft rounded-[28px] p-6">
                <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">Цены</p>
                <RegionalPriceList prices={regionalPrices} variant="detail" className="mt-4" />
                {formatDiscountEndDate(product.discountEnd) ? (
                  <p className="mt-5 text-sm text-amber-100/90">Скидка действует до {formatDiscountEndDate(product.discountEnd)}.</p>
                ) : null}
                <button
                  type="button"
                  className="btn-primary mt-6 w-full sm:w-auto"
                  onClick={openCheckout}
                  disabled={!checkoutPrices.length}
                >
                  <CreditCard size={16} />
                  {isAuthenticated ? 'Купить' : 'Войти и купить'}
                </button>
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
              <div className="panel-soft rounded-[28px] p-6">
                <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">Инфо</p>
                <ul className="mt-4 space-y-3 text-sm text-slate-300">
                  {(infoItems.length
                    ? infoItems
                    : ['Подробная информация из Telegram появится здесь, как только товар вернёт расширенные данные.']).map((item) => (
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
        availablePrices={checkoutPrices}
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
      />
    </div>
  )
}
