import { Pause, Play, PlayCircle, RefreshCw, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  cancelAdminPriceUpdate,
  fetchAdminPriceUpdateStatus,
  pauseAdminPriceUpdate,
  resumeAdminPriceUpdate,
  startAdminPriceUpdate,
} from '../../services/admin'
import type { AdminPriceUpdateStatus } from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import { AdminNotice, AdminSectionCard, EMPTY_ADMIN_NOTICE, type AdminNoticeState } from './AdminCommon'

export function AdminPricesSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [status, setStatus] = useState<AdminPriceUpdateStatus | null>(null)
  const [isStarting, setIsStarting] = useState<'test' | 'full' | null>(null)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)

  const isRunning = status?.status === 'pending' || status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const isActiveTask = isRunning || isPaused

  async function loadStatus() {
    try {
      setStatus(await fetchAdminPriceUpdateStatus())
    } catch {
      // тихо: статус не должен ронять секцию
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  useEffect(() => {
    if (!isActiveTask) return
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchAdminPriceUpdateStatus()
        setStatus(next)
        if (next.status === 'completed' || next.status === 'cancelled') {
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
      ? 'Тестовый запуск обработает первые 10 товаров из products.pkl. Запустить?'
      : 'Полное обновление цен пройдёт по всем ru-ua URL из products.pkl (несколько часов через прокси). Запустить?'

    if (!window.confirm(confirmText)) return

    setIsStarting(mode)
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const next = await startAdminPriceUpdate(test)
      setStatus(next)
      setNotice({ type: 'info', message: next.message || 'Обновление цен запущено.' })
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error, 'Не удалось запустить обновление цен.') })
    } finally {
      setIsStarting(null)
    }
  }

  return (
    <AdminSectionCard
      id="admin-prices"
      title="Обновление цен"
      description="Перепарсивает все товары из products.pkl и обновляет цены/скидки в БД. Можно поставить на паузу, продолжить и отменить — прогресс сохраняется в result.pkl каждые 100 товаров."
      action={
        <div className="flex flex-wrap gap-3">
          {isActiveTask ? (
            <>
              {isPaused ? (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={async () => setStatus(await resumeAdminPriceUpdate())}
                >
                  <PlayCircle size={16} />
                  Продолжить
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={async () => setStatus(await pauseAdminPriceUpdate())}
                >
                  <Pause size={16} />
                  Пауза
                </button>
              )}
              <button
                type="button"
                className="btn-secondary"
                onClick={async () => {
                  if (!window.confirm('Отменить обновление цен? Парсер допишет текущий батч и остановится.')) return
                  setStatus(await cancelAdminPriceUpdate())
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
                Обновить цены
              </button>
            </>
          )}
        </div>
      }
    >
      <AdminNotice state={notice} />
      <PriceUpdateStatusPanel status={status} />
    </AdminSectionCard>
  )
}

function PriceUpdateStatusPanel({ status }: { status: AdminPriceUpdateStatus | null }) {
  if (!status) return null

  const percent = Math.max(0, Math.min(100, Math.round(status.percent ?? 0)))
  const isActive = status.status === 'pending' || status.status === 'running' || status.status === 'paused'
  const logs = status.logs || []

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
        <MiniMetric label="Всего URL" value={status.total ?? '—'} />
        <MiniMetric label="Обработано" value={status.processed ?? 0} />
        <MiniMetric label="Осталось" value={status.remaining ?? '—'} />
        <MiniMetric label="Сохранено строк" value={status.saved ?? 0} />
        <MiniMetric label="Пустых ответов" value={status.failed ?? 0} />
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <span>{percent}%</span>
          <span>Режим: {status.mode === 'test' ? 'тест' : status.mode === 'full' ? 'полное' : '—'}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-white/8">
          <div
            className="h-full rounded-full bg-brand-400 transition-all"
            style={{ width: `${isActive ? Math.max(percent, 5) : percent}%` }}
          />
        </div>
      </div>

      <div className="mt-4 rounded-[14px] border border-white/8 bg-black/20">
        <div className="border-b border-white/8 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          Логи
        </div>
        <div className="max-h-52 space-y-2 overflow-auto px-3 py-3 text-xs leading-5 text-slate-300">
          {logs.length ? (
            logs
              .slice()
              .reverse()
              .map((log, index) => (
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

function MiniMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[12px] border border-white/8 bg-white/[0.03] p-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  )
}

function statusLabel(status: AdminPriceUpdateStatus | null) {
  if (!status || status.status === 'idle') return 'Не запущено'
  if (status.status === 'pending') return 'В очереди'
  if (status.status === 'running') return status.mode === 'test' ? 'Тестовый парсинг идёт' : 'Обновление идёт'
  if (status.status === 'paused') return 'На паузе'
  if (status.status === 'cancelled') return 'Отменено'
  if (status.status === 'completed') return 'Завершено'
  return 'Ошибка'
}

function formatLogTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 8)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
