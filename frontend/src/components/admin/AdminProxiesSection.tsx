import { Activity, ArrowRightCircle, CheckCircle2, RefreshCcw, RotateCw, ShieldOff, Wifi, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  checkAdminProxies,
  fetchAdminProxies,
  reloadAdminProxies,
  resetAdminProxy,
  rotateAdminProxy,
  selectAdminProxy,
} from '../../services/admin'
import type { AdminProxyEntry, AdminProxyStatus } from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import { AdminNotice, AdminSectionCard, EMPTY_ADMIN_NOTICE, type AdminNoticeState } from './AdminCommon'

export function AdminProxiesSection() {
  const [status, setStatus] = useState<AdminProxyStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)

  async function load() {
    setIsLoading(true)
    try {
      setStatus(await fetchAdminProxies())
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error, 'Не удалось получить статус прокси.') })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function withErrorHandling(label: string, action: () => Promise<AdminProxyStatus>) {
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      setStatus(await action())
      setNotice({ type: 'info', message: label + ' ✓' })
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error, `${label}: ошибка.`) })
    }
  }

  async function handleCheck() {
    setIsChecking(true)
    try {
      await withErrorHandling('Health-check всех прокси', checkAdminProxies)
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <AdminSectionCard
      id="admin-proxies"
      title="Прокси-пул"
      description="Список всех прокси из .env, статус каждого, ручная ротация и health-check к PS Store. При банах парсер автоматически переключается на следующий рабочий."
      action={
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={isLoading}
            onClick={() => withErrorHandling('Перечитать .env', reloadAdminProxies)}
          >
            <RefreshCcw size={16} />
            Перечитать .env
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={isChecking}
            onClick={handleCheck}
          >
            <Activity size={16} className={isChecking ? 'animate-pulse' : ''} />
            {isChecking ? 'Проверяю…' : 'Health-check'}
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={isLoading || (status?.size ?? 0) <= 1}
            onClick={() => withErrorHandling('Принудительная ротация', rotateAdminProxy)}
          >
            <RotateCw size={16} />
            Сменить активный
          </button>
        </div>
      }
    >
      <AdminNotice state={notice} />

      {!status ? (
        <p className="text-sm text-slate-400">Загружаю статус…</p>
      ) : !status.enabled ? (
        <div className="rounded-[18px] border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          Прокси выключены: <code className="text-amber-50">PARSER_USE_PROXY=false</code> или список пуст. Парсер
          ходит напрямую с IP сервера — это работает локально, но на VPS Akamai обычно банит.
        </div>
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-4">
            <Tile label="Всего прокси" value={status.size} />
            <Tile label="Активный" value={status.active_label || '—'} />
            <Tile label="Порог бана" value={`${status.ban_threshold} подряд 403`} />
            <Tile label="Cooldown" value={`${status.cooldown_seconds} сек`} />
          </div>

          <div className="space-y-2">
            {status.proxies.map((p) => (
              <ProxyRow
                key={p.label}
                entry={p}
                onSelect={() => withErrorHandling(`Активирован ${p.label}`, () => selectAdminProxy(p.label))}
                onReset={() => withErrorHandling(`Сброшен cooldown ${p.label}`, () => resetAdminProxy(p.label))}
              />
            ))}
          </div>
        </>
      )}
    </AdminSectionCard>
  )
}

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[16px] border border-white/10 bg-slate-950/40 p-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-base font-semibold text-white">{value}</p>
    </div>
  )
}

function ProxyRow({
  entry,
  onSelect,
  onReset,
}: {
  entry: AdminProxyEntry
  onSelect: () => Promise<void>
  onReset: () => Promise<void>
}) {
  const statusColor = entry.is_active
    ? 'border-emerald-400/30 bg-emerald-500/10'
    : entry.status === 'banned' || entry.status === 'failed_check'
      ? 'border-rose-400/30 bg-rose-500/8'
      : entry.status === 'cooldown'
        ? 'border-amber-400/30 bg-amber-500/8'
        : 'border-white/10 bg-white/[0.03]'

  const lastCheck = entry.last_check_at ? new Date(entry.last_check_at * 1000).toLocaleTimeString('ru-RU') : '—'
  const lastUsed = entry.last_used_at ? new Date(entry.last_used_at * 1000).toLocaleTimeString('ru-RU') : '—'

  return (
    <div className={`rounded-[14px] border ${statusColor} px-4 py-3`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <StatusIcon status={entry.status} isActive={entry.is_active} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">
              {entry.label}
              {entry.is_active ? <span className="ml-2 text-xs text-emerald-300">● активный</span> : null}
            </p>
            <p className="mt-0.5 text-xs text-slate-400">
              {statusLabel(entry.status)} · ok {entry.success_count} · fail {entry.fail_count}
              {entry.cooldown_seconds_left > 0 ? ` · cooldown: ${entry.cooldown_seconds_left}с` : ''}
            </p>
            {entry.last_error ? (
              <p className="mt-1 truncate text-xs text-rose-200/90">{entry.last_error}</p>
            ) : null}
            <p className="mt-1 text-[11px] text-slate-500">
              health-check: {lastCheck} · использовался: {lastUsed}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {!entry.is_active ? (
            <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={onSelect}>
              <ArrowRightCircle size={14} />
              Активировать
            </button>
          ) : null}
          {entry.fail_count > 0 || entry.status !== 'ok' ? (
            <button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={onReset}>
              <ShieldOff size={14} />
              Сброс cooldown
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function StatusIcon({ status, isActive }: { status: string; isActive: boolean }) {
  if (status === 'ok' || isActive) {
    return <CheckCircle2 size={20} className="flex-shrink-0 text-emerald-300" />
  }
  if (status === 'cooldown') {
    return <Activity size={20} className="flex-shrink-0 text-amber-300" />
  }
  if (status === 'banned' || status === 'failed_check') {
    return <XCircle size={20} className="flex-shrink-0 text-rose-300" />
  }
  return <Wifi size={20} className="flex-shrink-0 text-slate-400" />
}

function statusLabel(status: string) {
  if (status === 'ok') return 'OK'
  if (status === 'cooldown') return 'Cooldown'
  if (status === 'banned') return 'Banned (403)'
  if (status === 'failed_check') return 'Failed health-check'
  if (status === 'unknown') return 'Не проверялся'
  return status
}
