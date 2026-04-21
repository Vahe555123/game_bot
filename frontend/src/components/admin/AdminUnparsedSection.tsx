import { ExternalLink, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { fetchAdminUnparsedUrls, type AdminUnparsedUrlsResponse } from '../../services/admin'
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

export function AdminUnparsedSection() {
  const [data, setData] = useState<AdminUnparsedUrlsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [page, setPage] = useState(1)
  const [limit] = useState(100)
  const [mode, setMode] = useState<Mode>('missing_any')
  const [locale, setLocale] = useState('')
  const [search, setSearch] = useState('')

  async function load() {
    setIsLoading(true)
    try {
      const response = await fetchAdminUnparsedUrls({
        page,
        limit,
        mode,
        locale: locale || undefined,
        search: search.trim() || undefined,
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

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, limit, mode, locale])

  const totalPages = data ? Math.max(Math.ceil(data.unparsed_total / limit), 1) : 1

  return (
    <AdminSectionCard
      id="admin-unparsed"
      title="Не спарсенные URL из products.pkl"
      description="Сравнение products.pkl с таблицей products в БД: видно URL'ы, которые ещё не попали в каталог, и какие регионы у них не хватает."
      action={
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            setPage(1)
            load()
          }}
        >
          <RefreshCw size={16} />
          Обновить
        </button>
      }
    >
      <AdminNotice state={notice} />

      <div className="grid gap-3 md:grid-cols-[200px_200px_minmax(0,1fr)] mb-5">
        <select
          value={mode}
          onChange={(event) => {
            setPage(1)
            setMode(event.target.value as Mode)
          }}
          className="auth-input"
        >
          <option value="missing_any">Нет региона URL'а</option>
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
          placeholder="Поиск по URL (Enter)"
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
        <div className="hidden grid-cols-[minmax(0,1fr)_120px_180px_160px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
          <span>URL</span>
          <span>Локаль</span>
          <span>Есть регионы</span>
          <span>Нет регионов</span>
        </div>

        {isLoading ? (
          <div className="space-y-3 px-5 py-5">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="h-12 animate-pulse rounded-[16px] bg-white/[0.04]" />
            ))}
          </div>
        ) : data && data.items.length ? (
          <div className="divide-y divide-white/6">
            {data.items.map((item) => (
              <div
                key={item.url}
                className="grid gap-3 px-5 py-3 lg:grid-cols-[minmax(0,1fr)_120px_180px_160px] lg:items-center"
              >
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex min-w-0 items-center gap-2 text-sm text-brand-200 hover:text-brand-50"
                >
                  <ExternalLink size={14} className="shrink-0" />
                  <span className="truncate break-all">{item.url}</span>
                </a>
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
