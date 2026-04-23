import { ExternalLink, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  collectAdminUnparsedUrls,
  fetchAdminUnparsedUrlCollectionStatus,
  fetchAdminUnparsedUrls,
  fetchManualParseAdminProductStatus,
  manualParseAdminProduct,
  type AdminUnparsedUrlCollectionStatus,
  type AdminUnparsedUrlsResponse,
} from '../../services/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import {
  AdminEmptyState,
  AdminNotice,
  AdminSectionCard,
  AdminTableShell,
  EMPTY_ADMIN_NOTICE,
  type AdminNoticeState,
} from './AdminCommon'

const LOCALE_LABEL: Record<string, string> = {
  'ru-ua': '🇺🇦 UA',
  'en-tr': '🇹🇷 TR',
  'en-in': '🇮🇳 IN',
}

type Mode = 'missing_any' | 'missing_all' | 'all'
type RegionCountFilter = '' | '1' | '2'

export function AdminUnparsedSection() {
  const [data, setData] = useState<AdminUnparsedUrlsResponse | null>(null)
  const [collectionStatus, setCollectionStatus] = useState<AdminUnparsedUrlCollectionStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isCollecting, setIsCollecting] = useState(false)
  const [reparsingUrl, setReparsingUrl] = useState<string | null>(null)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [page, setPage] = useState(1)
  const [limit] = useState(100)
  const [mode, setMode] = useState<Mode>('missing_any')
  const [locale, setLocale] = useState('')
  const [regionCount, setRegionCount] = useState<RegionCountFilter>('')
  const [search, setSearch] = useState('')

  const collectionRunning = collectionStatus?.status === 'pending' || collectionStatus?.status === 'running'

  async function load() {
    setIsLoading(true)
    try {
      const response = await fetchAdminUnparsedUrls({
        page,
        limit,
        mode,
        locale: locale || undefined,
        search: search.trim() || undefined,
        region_count: regionCount ? Number(regionCount) : undefined,
      })
      setData(response)
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить список не спарсенных URL.'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  async function loadCollectionStatus() {
    try {
      setCollectionStatus(await fetchAdminUnparsedUrlCollectionStatus())
    } catch {
      // Статус сбора не критичен для просмотра таблицы.
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, limit, mode, locale, regionCount])

  useEffect(() => {
    loadCollectionStatus()
  }, [])

  useEffect(() => {
    if (!collectionRunning) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const status = await fetchAdminUnparsedUrlCollectionStatus()
        setCollectionStatus(status)
        if (status.status === 'completed') {
          await load()
        }
      } catch {
        window.clearInterval(timer)
      }
    }, 2500)

    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionRunning])

  async function handleCollectUrls() {
    setIsCollecting(true)
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const status = await collectAdminUnparsedUrls()
      setCollectionStatus(status)
      if (status.status === 'completed') {
        await load()
      }
      setNotice({
        type: status.status === 'failed' ? 'error' : 'success',
        message: status.message || 'Сбор URL запущен.',
      })
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось запустить сбор URL.'),
      })
    } finally {
      setIsCollecting(false)
    }
  }

  async function handleReparseUa(item: AdminUnparsedUrlsResponse['items'][number]) {
    const uaUrl = item.ua_url || `https://store.playstation.com/ru-ua/product/${item.product_id}`
    const label = item.product_name || item.product_id

    if (!window.confirm(`Запустить репарс UA для "${label}"?\n${uaUrl}`)) {
      return
    }

    setReparsingUrl(item.url)
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const start = await manualParseAdminProduct({
        ua_url: uaUrl,
        tr_url: null,
        in_url: null,
        save_to_db: true,
      })
      const response = await waitManualParse(start.task_id)
      setNotice({
        type: 'success',
        message: `Репарс готов: ${response.final_total} записей, добавлено ${response.added_count}, обновлено ${response.updated_count}.`,
      })
      await load()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось выполнить репарс UA.'),
      })
    } finally {
      setReparsingUrl(null)
    }
  }

  const totalPages = data ? Math.max(Math.ceil(data.unparsed_total / limit), 1) : 1

  return (
    <AdminSectionCard
      id="admin-unparsed"
      title="Не спарсенные URL из products.pkl"
      description="Сравнение products.pkl с таблицей products в БД: видно URL, которые ещё не попали в каталог, и какие регионы у них не хватает."
      action={
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={isCollecting || collectionRunning}
            onClick={handleCollectUrls}
          >
            <RefreshCw size={16} className={isCollecting || collectionRunning ? 'animate-spin' : ''} />
            Собрать URL
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              setPage(1)
              load()
              loadCollectionStatus()
            }}
          >
            <RefreshCw size={16} />
            Обновить
          </button>
        </div>
      }
    >
      <AdminNotice state={notice} />
      <UrlCollectionStatus status={collectionStatus} />

      <div className="mb-5 grid gap-3 md:grid-cols-[200px_200px_180px_minmax(0,1fr)]">
        <select
          value={mode}
          onChange={(event) => {
            setPage(1)
            setMode(event.target.value as Mode)
          }}
          className="auth-input"
        >
          <option value="missing_any">Нет региона URL&apos;а</option>
          <option value="missing_all">Нет ни одного региона</option>
          <option value="all">Все URL</option>
        </select>

        <select
          value={locale}
          onChange={(event) => {
            setPage(1)
            setLocale(event.target.value)
          }}
          className="auth-input"
        >
          <option value="">Все локали</option>
          <option value="ru-ua">🇺🇦 ru-ua</option>
          <option value="en-tr">🇹🇷 en-tr</option>
          <option value="en-in">🇮🇳 en-in</option>
        </select>

        <select
          value={regionCount}
          onChange={(event) => {
            setPage(1)
            setRegionCount(event.target.value as RegionCountFilter)
          }}
          className="auth-input"
        >
          <option value="">Все регионы</option>
          <option value="1">Есть 1 регион</option>
          <option value="2">Есть 2 региона</option>
        </select>

        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              setPage(1)
              load()
            }
          }}
          className="auth-input"
          placeholder="Поиск по URL, ID или названию (Enter)"
        />
      </div>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryTile label="Всего в products.pkl" value={data?.total_urls_in_pkl ?? '—'} />
        <SummaryTile label="ID в БД (каталог)" value={data?.parsed_ids ?? '—'} />
        <SummaryTile label="Не спарсено (по фильтру)" value={data?.unparsed_total ?? '—'} />
        <SummaryTile
          label="По локалям (не спарсено)"
          value={
            data && data.missing_by_locale
              ? Object.entries(data.missing_by_locale)
                  .map(([loc, count]) => `${LOCALE_LABEL[loc] || loc}: ${count}`)
                  .join(' • ') || '—'
              : '—'
          }
          small
        />
      </div>

      <AdminTableShell>
        <div className="hidden grid-cols-[minmax(0,1.4fr)_120px_150px_150px_140px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
          <span>Игра / URL</span>
          <span>Локаль</span>
          <span>Есть регионы</span>
          <span>Нет регионов</span>
          <span>Действие</span>
        </div>

        {isLoading ? (
          <div className="space-y-3 px-5 py-5">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="h-14 animate-pulse rounded-[16px] bg-white/[0.04]" />
            ))}
          </div>
        ) : data && data.items.length ? (
          <div className="divide-y divide-white/6">
            {data.items.map((item) => (
              <div
                key={item.url}
                className="grid gap-3 px-5 py-3 lg:grid-cols-[minmax(0,1.4fr)_120px_150px_150px_140px] lg:items-center"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">
                    {item.product_name || 'Название пока не найдено'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    ID: {item.product_id} {item.added_at ? `• добавлено ${formatDate(item.added_at)}` : ''}
                  </p>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 flex min-w-0 items-center gap-2 text-xs text-brand-200 hover:text-brand-50"
                  >
                    <ExternalLink size={13} className="shrink-0" />
                    <span className="truncate break-all">{item.url}</span>
                  </a>
                </div>
                <div className="text-xs text-slate-300">{LOCALE_LABEL[item.locale] || item.locale}</div>
                <div className="flex flex-wrap gap-1">
                  {item.exists_in_regions.length ? (
                    item.exists_in_regions.map((region) => (
                      <span
                        key={region}
                        className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-100"
                      >
                        {region}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">—</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1">
                  {item.missing_regions.map((region) => (
                    <span
                      key={region}
                      className="rounded-full border border-rose-400/20 bg-rose-500/10 px-2 py-0.5 text-[11px] text-rose-100"
                    >
                      {region}
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  className="btn-secondary px-3 py-2 text-xs"
                  disabled={Boolean(reparsingUrl)}
                  onClick={() => handleReparseUa(item)}
                >
                  <RefreshCw size={14} className={reparsingUrl === item.url ? 'animate-spin' : ''} />
                  Репарс UA
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-5 py-8">
            <AdminEmptyState
              title="Нет подходящих URL"
              description="Попробуйте сменить фильтр или проверьте, что products.pkl лежит в корне проекта."
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
    </AdminSectionCard>
  )
}

async function waitManualParse(taskId: string) {
  const maxPollAttempts = 360

  for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
    const status = await fetchManualParseAdminProductStatus(taskId)

    if (status.status === 'completed' && status.result) {
      return status.result
    }

    if (status.status === 'failed') {
      throw new Error(status.message || 'Ручной парсинг завершился с ошибкой.')
    }

    await new Promise((resolve) => window.setTimeout(resolve, 2000))
  }

  throw new Error('Превышено время ожидания завершения ручного парсинга.')
}

function UrlCollectionStatus({ status }: { status: AdminUnparsedUrlCollectionStatus | null }) {
  if (!status) {
    return null
  }

  const isActive = status.status === 'pending' || status.status === 'running'
  const newProducts = status.new_products || []

  return (
    <div className="mb-5 rounded-[18px] border border-white/10 bg-slate-950/40 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-white">
            {isActive ? 'Сбор URL идёт' : status.status === 'failed' ? 'Сбор URL упал' : 'Сбор URL'}
          </p>
          <p className="mt-1 text-sm text-slate-300">{status.message}</p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
          {status.phase || status.status}
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MiniMetric label="В products.pkl" value={status.total_urls ?? '—'} />
        <MiniMetric label="Найдено URL" value={status.raw_urls ?? '—'} />
        <MiniMetric label="Развёрнуто" value={status.expanded_urls ?? '—'} />
        <MiniMetric label="Осталось" value={status.remaining ?? '—'} />
        <MiniMetric label="Новых" value={status.new_products_count ?? '—'} />
      </div>

      {isActive ? (
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/8">
          <div
            className="h-full rounded-full bg-brand-400 transition-all"
            style={{ width: `${computeProgressPercent(status)}%` }}
          />
        </div>
      ) : null}

      {newProducts.length ? (
        <details className="mt-4 text-sm text-slate-300">
          <summary className="cursor-pointer text-brand-100">Новые продукты ({status.new_products_count})</summary>
          <div className="mt-3 max-h-48 space-y-2 overflow-auto rounded-[12px] border border-white/8 bg-black/20 p-3">
            {newProducts.map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="block truncate text-xs text-brand-200 hover:text-brand-50"
              >
                {url}
              </a>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  )
}

function SummaryTile({
  label,
  value,
  small = false,
}: {
  label: string
  value: string | number
  small?: boolean
}) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-slate-950/50 p-4">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className={small ? 'mt-2 text-sm leading-6 text-slate-200' : 'mt-2 text-xl font-semibold text-white'}>
        {value}
      </p>
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

function computeProgressPercent(status: AdminUnparsedUrlCollectionStatus) {
  if (status.phase === 'product_urls' && status.total_pages) {
    return Math.min(Math.round(((status.processed_pages || 0) / status.total_pages) * 100), 100)
  }
  if (status.phase === 'expand' && status.total_concepts) {
    return Math.min(Math.round(((status.processed_concepts || 0) / status.total_concepts) * 100), 100)
  }
  return status.status === 'completed' ? 100 : 8
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
