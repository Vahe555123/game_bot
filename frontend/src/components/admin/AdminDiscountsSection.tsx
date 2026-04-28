import { BadgePercent, CalendarX, ExternalLink, Pause, Play, PlayCircle, RefreshCw, Send, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  cancelAdminDiscountUpdate,
  clearAdminDiscountsByDates,
  fetchAdminDiscountExpiryGroups,
  fetchAdminDiscountProducts,
  fetchAdminDiscountUpdateStatus,
  pauseAdminDiscountUpdate,
  resumeAdminDiscountUpdate,
  sendAdminDiscountNotifications,
  startAdminDiscountUpdate,
} from '../../services/admin'
import type { AdminDiscountExpiryGroup } from '../../services/admin'
import type { AdminDiscountUpdateStatus, AdminProduct } from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import {
  AdminEmptyState,
  AdminNotice,
  AdminSectionCard,
  AdminTableShell,
  EMPTY_ADMIN_NOTICE,
  type AdminNoticeState,
} from './AdminCommon'

type RegionFilter = '' | 'UA' | 'TR' | 'IN'

const REGION_LOCALE: Record<AdminProduct['region'], string> = {
  UA: 'ru-ua',
  TR: 'en-tr',
  IN: 'en-in',
}

export function AdminDiscountsSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [products, setProducts] = useState<AdminProduct[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(12)
  const [search, setSearch] = useState('')
  const [region, setRegion] = useState<RegionFilter>('')
  const [status, setStatus] = useState<AdminDiscountUpdateStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isStarting, setIsStarting] = useState<'test' | 'full' | null>(null)
  const [isSendingNotifications, setIsSendingNotifications] = useState(false)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [isExpiryModalOpen, setIsExpiryModalOpen] = useState(false)

  const isRunning = status?.status === 'pending' || status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const isActiveTask = isRunning || isPaused

  async function loadProducts() {
    setIsLoading(true)
    try {
      const response = await fetchAdminDiscountProducts({
        page,
        limit,
        search: search.trim() || undefined,
        region: region || undefined,
      })
      setProducts(response.products)
      setTotal(response.total)
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить товары со скидками.'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  async function loadStatus() {
    try {
      setStatus(await fetchAdminDiscountUpdateStatus())
    } catch {
      // Статус парсера не должен ломать просмотр списка скидок.
    }
  }

  useEffect(() => {
    loadProducts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, limit, region])

  useEffect(() => {
    loadStatus()
  }, [])

  useEffect(() => {
    if (!isActiveTask) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const nextStatus = await fetchAdminDiscountUpdateStatus()
        setStatus(nextStatus)
        if (nextStatus.status === 'completed' || nextStatus.status === 'cancelled') {
          await loadProducts()
          await onDataChanged()
        }
      } catch {
        window.clearInterval(timer)
      }
    }, 2500)

    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActiveTask])

  async function handleStart(test: boolean) {
    const mode = test ? 'test' : 'full'
    const confirmText = test
      ? 'Тестовый запуск UPSERT-нет первые 10 товаров sale-раздела. Старые скидки трогать не будет — истёкшие удалит фоновая задача. Запустить?'
      : 'Полное обновление UPSERT-нет весь sale-раздел. Старые скидки с актуальной датой останутся, истёкшие удалит фоновая задача. Запустить?'

    if (!window.confirm(confirmText)) {
      return
    }

    setIsStarting(mode)
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const nextStatus = await startAdminDiscountUpdate(test)
      setStatus(nextStatus)
      setNotice({
        type: 'info',
        message: nextStatus.message || 'Обновление скидок запущено.',
      })
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось запустить обновление скидок.'),
      })
    } finally {
      setIsStarting(null)
    }
  }

  async function handleSendNotifications() {
    if (
      !window.confirm(
        'Отправить уведомления по текущим скидкам вручную? Кнопка выполнит повторную отправку для email и Telegram.',
      )
    ) {
      return
    }

    setIsSendingNotifications(true)
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const response = await sendAdminDiscountNotifications()
      setNotice({
        type: response.summary.failed ? 'info' : 'success',
        message: response.message,
      })
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось отправить уведомления по скидкам.'),
      })
    } finally {
      setIsSendingNotifications(false)
    }
  }

  const totalPages = Math.max(Math.ceil(total / limit), 1)

  return (
    <AdminSectionCard
      id="admin-discounts"
      title="Скидки"
      description="Товары, у которых сейчас есть скидка в базе, и запуск отдельного процесса обновления скидок из PlayStation Store."
      action={
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={Boolean(isStarting) || isSendingNotifications || isActiveTask}
            onClick={() => setIsExpiryModalOpen(true)}
          >
            <CalendarX size={16} />
            Очистить по дате
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={Boolean(isStarting) || isSendingNotifications || isActiveTask}
            onClick={handleSendNotifications}
          >
            {isSendingNotifications ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
            Отправить уведомления
          </button>
          {isActiveTask ? (
            <>
              {isPaused ? (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={async () => setStatus(await resumeAdminDiscountUpdate())}
                >
                  <PlayCircle size={16} />
                  Продолжить
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={async () => setStatus(await pauseAdminDiscountUpdate())}
                >
                  <Pause size={16} />
                  Пауза
                </button>
              )}
              <button
                type="button"
                className="btn-secondary"
                onClick={async () => {
                  if (!window.confirm('Отменить обновление скидок? Парсер допишет текущий батч и остановится.')) return
                  setStatus(await cancelAdminDiscountUpdate())
                }}
              >
                <X size={16} />
                Отменить
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn-secondary"
                disabled={Boolean(isStarting)}
                onClick={() => handleStart(true)}
              >
                <Play size={16} className={isStarting === 'test' ? 'animate-spin' : ''} />
                Тест 10 товаров
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={Boolean(isStarting)}
                onClick={() => handleStart(false)}
              >
                <RefreshCw size={16} className={isStarting === 'full' ? 'animate-spin' : ''} />
                Обновить скидки
              </button>
            </>
          )}
        </div>
      }
    >
      <AdminNotice state={notice} />
      <DiscountUpdateStatusPanel status={status} />

      <div className="mb-5 grid gap-3 md:grid-cols-[180px_minmax(0,1fr)_auto]">
        <select
          value={region}
          onChange={(event) => {
            setPage(1)
            setRegion(event.target.value as RegionFilter)
          }}
          className="auth-input"
        >
          <option value="">Все регионы</option>
          <option value="UA">UA</option>
          <option value="TR">TR</option>
          <option value="IN">IN</option>
        </select>

        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              setPage(1)
              loadProducts()
            }
          }}
          className="auth-input"
          placeholder="Поиск по названию, ID или издателю (Enter)"
        />

        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            loadProducts()
            loadStatus()
          }}
        >
          <RefreshCw size={16} />
          Обновить
        </button>
      </div>

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <SummaryTile label="Товаров со скидкой" value={total} />
        <SummaryTile label="Страница" value={`${page}/${totalPages}`} />
        <SummaryTile label="Процесс" value={statusLabel(status)} />
      </div>

      <AdminTableShell>
        <div className="hidden grid-cols-[minmax(0,1.4fr)_90px_120px_180px_130px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
          <span>Товар</span>
          <span>Регион</span>
          <span>Скидка</span>
          <span>Цена</span>
          <span>PS Store</span>
        </div>

        {isLoading ? (
          <div className="space-y-3 px-5 py-5">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="h-14 animate-pulse rounded-[16px] bg-white/[0.04]" />
            ))}
          </div>
        ) : products.length ? (
          <div className="divide-y divide-white/6">
            {products.map((product) => (
              <div
                key={`${product.id}-${product.region}`}
                className="grid gap-3 px-5 py-3 lg:grid-cols-[minmax(0,1.4fr)_90px_120px_180px_130px] lg:items-center"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{product.display_name}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">
                    {product.id} {product.discount_end ? `• до ${formatDate(product.discount_end)}` : ''}
                  </p>
                </div>
                <span className="text-sm text-slate-300">{product.region}</span>
                <div className="inline-flex w-fit items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1 text-sm font-semibold text-emerald-100">
                  <BadgePercent size={15} />
                  -{Math.round(product.discount || 0)}%
                </div>
                <div className="text-sm text-slate-300">
                  <span>{formatRegionalPrice(product)}</span>
                  {formatRegionalOldPrice(product) ? (
                    <span className="ml-2 text-xs text-slate-500 line-through">{formatRegionalOldPrice(product)}</span>
                  ) : null}
                </div>
                <a
                  href={buildProductUrl(product)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex w-fit items-center gap-2 text-sm text-brand-200 hover:text-brand-50"
                >
                  <ExternalLink size={15} />
                  Открыть
                </a>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-5 py-8">
            <AdminEmptyState
              title="Скидок пока нет"
              description="После запуска обновления здесь появятся товары, у которых парсер нашёл скидку."
            />
          </div>
        )}
      </AdminTableShell>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-400">
          Страница {page} из {totalPages}
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(current - 1, 1))}
          >
            Назад
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={page >= totalPages}
            onClick={() => setPage((current) => Math.min(current + 1, totalPages))}
          >
            Вперёд
          </button>
        </div>
      </div>

      {isExpiryModalOpen ? (
        <DiscountExpiryModal
          onClose={() => setIsExpiryModalOpen(false)}
          onCleared={async (response) => {
            setNotice({
              type: 'success',
              message:
                `Очищено: products=${response.products_cleared}, ` +
                `product_cards=${response.product_cards_cleared}, ` +
                `result.pkl=${response.result_cache_cleared}.`,
            })
            setIsExpiryModalOpen(false)
            await loadProducts()
            await onDataChanged()
          }}
        />
      ) : null}
    </AdminSectionCard>
  )
}

function DiscountExpiryModal({
  onClose,
  onCleared,
}: {
  onClose: () => void
  onCleared: (response: Awaited<ReturnType<typeof clearAdminDiscountsByDates>>) => Promise<void> | void
}) {
  const [groups, setGroups] = useState<AdminDiscountExpiryGroup[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [isClearing, setIsClearing] = useState(false)
  const [confirmStep, setConfirmStep] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchAdminDiscountExpiryGroups()
        if (!cancelled) setGroups(data)
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err, 'Не удалось загрузить группы скидок.'))
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const totalProducts = groups
    .filter((group) => selected.has(group.discount_end))
    .reduce((sum, group) => sum + group.products_count, 0)
  const totalRows = groups
    .filter((group) => selected.has(group.discount_end))
    .reduce((sum, group) => sum + group.rows_count, 0)

  function toggle(date: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(date)) next.delete(date)
      else next.add(date)
      return next
    })
    setConfirmStep(false)
  }

  async function handleClear() {
    if (!confirmStep) {
      setConfirmStep(true)
      return
    }
    setIsClearing(true)
    setError(null)
    try {
      const response = await clearAdminDiscountsByDates(Array.from(selected))
      await onCleared(response)
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось очистить скидки.'))
      setConfirmStep(false)
    } finally {
      setIsClearing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8">
      <div className="w-full max-w-2xl rounded-[24px] border border-white/10 bg-slate-950/95 p-6 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Очистка скидок по дате окончания</h3>
            <p className="mt-1 text-sm text-slate-400">
              Выберите одну или несколько дат `discount_end`. Очистятся только товары с этими метками
              в `products`, `product_cards` и `result.pkl`. Остальные скидки не пострадают.
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        {error ? (
          <div className="mb-3 rounded-[12px] border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">
            {error}
          </div>
        ) : null}

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-12 animate-pulse rounded-[12px] bg-white/[0.04]" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <div className="rounded-[12px] border border-white/10 bg-white/[0.03] px-4 py-6 text-center text-sm text-slate-400">
            В каталоге нет скидок с заполненной датой окончания.
          </div>
        ) : (
          <div className="max-h-80 space-y-2 overflow-auto pr-1">
            {groups.map((group) => {
              const checked = selected.has(group.discount_end)
              return (
                <label
                  key={group.discount_end}
                  className={`flex cursor-pointer items-center justify-between gap-3 rounded-[14px] border px-4 py-3 text-sm transition ${
                    checked
                      ? 'border-brand-400/60 bg-brand-500/10 text-white'
                      : 'border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]'
                  }`}
                >
                  <span className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(group.discount_end)}
                      className="h-4 w-4 accent-brand-400"
                    />
                    <span>
                      <span className="font-mono text-sm">{group.discount_end}</span>
                      <span className="ml-2 text-xs text-slate-400">UTC</span>
                    </span>
                  </span>
                  <span className="text-xs text-slate-300">
                    {group.products_count} товаров • {group.rows_count} строк
                  </span>
                </label>
              )
            })}
          </div>
        )}

        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-300">
            Выбрано дат: <span className="font-semibold text-white">{selected.size}</span>
            {selected.size ? (
              <>
                {' '}
                • товаров: <span className="font-semibold text-white">{totalProducts}</span>
                {' '}• строк: <span className="font-semibold text-white">{totalRows}</span>
              </>
            ) : null}
          </p>
          <div className="flex gap-3">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isClearing}>
              Отмена
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={selected.size === 0 || isClearing}
              onClick={handleClear}
            >
              {isClearing ? <RefreshCw size={16} className="animate-spin" /> : <Trash2 size={16} />}
              {confirmStep ? 'Точно удалить?' : 'Удалить выбранные'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function DiscountUpdateStatusPanel({ status }: { status: AdminDiscountUpdateStatus | null }) {
  if (!status) {
    return null
  }

  const percent = Math.max(0, Math.min(100, Math.round(status.percent ?? 0)))
  const isActive = status.status === 'pending' || status.status === 'running'
  const logs = status.logs || []
  const notificationSummary = status.notification_summary

  return (
    <div className="mb-5 rounded-[18px] border border-white/10 bg-slate-950/40 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-white">{statusLabel(status)}</p>
          <p className="mt-1 text-sm text-slate-300">{status.message}</p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
          {status.phase || status.status}
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MiniMetric label="Всего игр" value={status.total ?? '—'} />
        <MiniMetric label="Обновлено" value={status.processed ?? 0} />
        <MiniMetric label="Осталось" value={status.remaining ?? '—'} />
        <MiniMetric label="Строк в БД" value={status.saved ?? 0} />
        <MiniMetric label="Ошибок" value={status.failed ?? 0} />
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <span>{percent}%</span>
          <span>Скидочных строк: {status.discount_records ?? 0}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-white/8">
          <div
            className="h-full rounded-full bg-brand-400 transition-all"
            style={{ width: `${isActive ? Math.max(percent, 5) : percent}%` }}
          />
        </div>
      </div>

      {notificationSummary ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-300">
          <span className="rounded-full border border-white/10 px-3 py-1">
            Уведомления: {notificationSummary.sent ?? 0}
          </span>
          <span className="rounded-full border border-white/10 px-3 py-1">
            Email: {notificationSummary.email_sent ?? 0}
          </span>
          <span className="rounded-full border border-white/10 px-3 py-1">
            Telegram: {notificationSummary.telegram_sent ?? 0}
          </span>
          <span className="rounded-full border border-white/10 px-3 py-1">
            Ошибок: {notificationSummary.failed ?? 0}
          </span>
        </div>
      ) : null}

      <div className="mt-4 rounded-[14px] border border-white/8 bg-black/20">
        <div className="border-b border-white/8 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          Логи
        </div>
        <div className="max-h-52 space-y-2 overflow-auto px-3 py-3 text-xs leading-5 text-slate-300">
          {logs.length ? (
            logs.slice().reverse().map((log, index) => (
              <div key={`${log.time}-${index}`} className="grid gap-2 sm:grid-cols-[80px_minmax(0,1fr)]">
                <span className="text-slate-500">{formatLogTime(log.time)}</span>
                <span>{log.message}</span>
              </div>
            ))
          ) : (
            <p className="text-slate-500">Логов пока нет.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function SummaryTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-slate-950/50 p-4">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  )
}

function MiniMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[12px] border border-white/8 bg-white/[0.03] p-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  )
}

function statusLabel(status: AdminDiscountUpdateStatus | null) {
  if (!status || status.status === 'idle') return 'Не запущено'
  if (status.status === 'pending') return 'В очереди'
  if (status.status === 'running') return status.mode === 'test' ? 'Тестовый парсинг идёт' : 'Обновление идёт'
  if (status.status === 'paused') return 'На паузе'
  if (status.status === 'cancelled') return 'Отменено'
  if (status.status === 'completed') return 'Завершено'
  return 'Ошибка'
}

function buildProductUrl(product: AdminProduct) {
  const locale = REGION_LOCALE[product.region] || 'ru-ua'
  return `https://store.playstation.com/${locale}/product/${product.id}`
}

function formatRegionalPrice(product: AdminProduct) {
  if (product.region === 'UA') return formatPrice(product.price_uah, 'UAH')
  if (product.region === 'TR') return formatPrice(product.price_try, 'TRY')
  return formatPrice(product.price_inr, 'INR')
}

function formatRegionalOldPrice(product: AdminProduct) {
  if (product.region === 'UA') return formatPrice(product.old_price_uah, 'UAH')
  if (product.region === 'TR') return formatPrice(product.old_price_try, 'TRY')
  return formatPrice(product.old_price_inr, 'INR')
}

function formatPrice(value?: number | null, currency?: string) {
  if (!value) {
    return ''
  }
  return `${new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value)} ${currency || ''}`.trim()
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleDateString('ru-RU')
}

function formatLogTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 8)
  }
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
