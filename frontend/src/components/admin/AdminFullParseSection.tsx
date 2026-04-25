import { AlertTriangle, Pause, Play, PlayCircle, RefreshCw, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  cancelAdminFullParse,
  fetchAdminFullParseStatus,
  pauseAdminFullParse,
  resumeAdminFullParse,
  resumeAdminFullParseTask,
  startAdminFullParse,
} from '../../services/admin'
import type { AdminFullParseOrphanTask, AdminFullParseStatus } from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import { AdminNotice, AdminSectionCard, EMPTY_ADMIN_NOTICE, type AdminNoticeState } from './AdminCommon'

export function AdminFullParseSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [status, setStatus] = useState<AdminFullParseStatus | null>(null)
  const [isStarting, setIsStarting] = useState<'test' | 'full' | null>(null)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)

  const isRunning = status?.status === 'pending' || status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const isActiveTask = isRunning || isPaused
  const orphanTasks = status?.orphans || []

  async function loadStatus() {
    try {
      setStatus(await fetchAdminFullParseStatus())
    } catch {
      // тихо
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  useEffect(() => {
    if (!isActiveTask) return
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchAdminFullParseStatus()
        setStatus(next)
        if (next.status === 'completed' || next.status === 'cancelled') {
          await onDataChanged()
        }
      } catch {
        window.clearInterval(timer)
      }
    }, 2000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActiveTask])

  async function handleStart(test: boolean) {
    const mode = test ? 'test' : 'full'
    const confirmText = test
      ? 'Тестовый полный парсинг — 100 случайных товаров. БД не очищается, обновятся только цены/скидки. Запустить?'
      : 'ПОЛНЫЙ парсинг по всем товарам из products.pkl — много часов через прокси. БД не очищается, обновляются только цены/скидки. Запустить?'

    if (!window.confirm(confirmText)) return

    setIsStarting(mode)
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const next = await startAdminFullParse(test)
      setStatus(next)
      setNotice({ type: 'info', message: next.message || 'Полный парсинг запущен.' })
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error, 'Не удалось запустить полный парсинг.') })
    } finally {
      setIsStarting(null)
    }
  }

  return (
    <AdminSectionCard
      id="admin-full-parse"
      title="Полный парсинг"
      description="Парсинг всех товаров через PS Store с защитой от банов: пауза/продолжить/отмена, прогресс по регионам, счётчик 403'ок (вероятный бан прокси). Тестовый режим — 100 случайных товаров без риска для базы."
      action={
        <div className="flex flex-wrap gap-3">
          {isActiveTask ? (
            <>
              {isPaused ? (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={async () => setStatus(await resumeAdminFullParse())}
                >
                  <PlayCircle size={16} />
                  Продолжить
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={async () => setStatus(await pauseAdminFullParse())}
                >
                  <Pause size={16} />
                  Пауза
                </button>
              )}
              <button
                type="button"
                className="btn-secondary"
                onClick={async () => {
                  if (!window.confirm('Отменить полный парсинг? Парсер допишет текущий батч и остановится.')) return
                  setStatus(await cancelAdminFullParse())
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
                Тест 100 товаров
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={Boolean(isStarting)}
                onClick={() => handleStart(false)}
              >
                <RefreshCw size={16} className={isStarting === 'full' ? 'animate-spin' : ''} />
                Полный парсинг
              </button>
            </>
          )}
        </div>
      }
    >
      <AdminNotice state={notice} />
      {!isActiveTask && orphanTasks.length ? (
        <div className="mb-5 rounded-[18px] border border-amber-400/20 bg-amber-500/10 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-200" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-amber-50">Найдены незавершённые задачи после рестарта</p>
              <p className="mt-1 text-sm text-amber-100/90">
                Можно продолжить последний полный парсинг с сохранённого checkpoint, без старта с нуля.
              </p>
              <div className="mt-3 space-y-2">
                {orphanTasks.map((task) => (
                  <OrphanTaskRow
                    key={task.task_id}
                    task={task}
                    onResume={async () => {
                      setNotice(EMPTY_ADMIN_NOTICE)
                      try {
                        const next = await resumeAdminFullParseTask(task.task_id)
                        setStatus(next)
                        setNotice({ type: 'info', message: 'Продолжаю незавершённый полный парсинг.' })
                      } catch (error) {
                        setNotice({
                          type: 'error',
                          message: getApiErrorMessage(error, 'Не удалось продолжить незавершённый парсинг.'),
                        })
                      }
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
      <FullParseStatusPanel status={status} />
    </AdminSectionCard>
  )
}

function FullParseStatusPanel({ status }: { status: AdminFullParseStatus | null }) {
  if (!status) return null

  const percent = Math.max(0, Math.min(100, Math.round(status.percent ?? 0)))
  const isActive = status.status === 'pending' || status.status === 'running' || status.status === 'paused'
  const logs = status.logs || []
  const banWarning = (status.consecutive_bans ?? 0) >= 5

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

      {banWarning ? (
        <div className="mt-3 flex items-start gap-2 rounded-[14px] border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
          <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
          <span>
            Прокси, вероятно, забанили — {status.consecutive_bans} подряд 403'ок от Akamai. Парсер делает 60-секундную
            паузу. Если ситуация повторяется — смените прокси в .env и перезапустите.
          </span>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MiniMetric label="Всего" value={status.total ?? '—'} />
        <MiniMetric label="Обработано" value={status.processed ?? 0} />
        <MiniMetric label="Осталось" value={status.remaining ?? '—'} />
        <MiniMetric label="Сохранено строк" value={status.saved ?? 0} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MiniMetric label="Пустых ответов" value={status.empty_returns ?? 0} accent="muted" />
        <MiniMetric label="403 / Akamai" value={status.ban_count_403 ?? 0} accent="danger" />
        <MiniMetric label="Ошибок" value={status.failed ?? 0} accent="danger" />
        <MiniMetric
          label="Скорость"
          value={status.avg_per_product_seconds ? `${status.avg_per_product_seconds}c/товар` : '—'}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <MiniMetric label="Без UA" value={status.missing_ua ?? 0} accent="muted" />
        <MiniMetric label="Без TR" value={status.missing_tr ?? 0} accent="muted" />
        <MiniMetric label="Без IN" value={status.missing_in ?? 0} accent="muted" />
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <span>{percent}%</span>
          <span>Режим: {status.mode === 'test' ? 'тест 100' : status.mode === 'full' ? 'полный' : '—'}</span>
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
        <div className="max-h-72 space-y-2 overflow-auto px-3 py-3 text-xs leading-5 text-slate-300">
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

function MiniMetric({
  label,
  value,
  accent,
}: {
  label: string
  value: string | number
  accent?: 'danger' | 'muted'
}) {
  const colour =
    accent === 'danger' && Number(value) > 0
      ? 'text-rose-200'
      : accent === 'muted'
        ? 'text-slate-300'
        : 'text-white'
  return (
    <div className="rounded-[12px] border border-white/8 bg-white/[0.03] p-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${colour}`}>{value}</p>
    </div>
  )
}

function OrphanTaskRow({
  task,
  onResume,
}: {
  task: AdminFullParseOrphanTask
  onResume: () => Promise<void>
}) {
  const updatedAt = task.updated_at ? formatLogTime(task.updated_at) : '—'
  const total = task.total ?? '—'
  const processed = task.processed ?? 0
  const saved = task.saved_total ?? 0
  const failed = task.failed_total ?? 0

  return (
    <div className="flex flex-col gap-3 rounded-[14px] border border-white/10 bg-slate-950/35 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-white">
          {task.mode === 'test' ? 'Тест 100' : 'Полный парсинг'} · {task.task_id.slice(0, 8)}
        </p>
        <p className="mt-1 text-xs text-slate-300">
          Обработано {processed}/{total} · Сохранено {saved} · Ошибок {failed} · Обновлено {updatedAt}
        </p>
      </div>
      <button type="button" className="btn-secondary shrink-0" onClick={onResume}>
        <PlayCircle size={16} />
        Продолжить
      </button>
    </div>
  )
}

function statusLabel(status: AdminFullParseStatus | null) {
  if (!status || status.status === 'idle') return 'Не запущено'
  if (status.status === 'pending') return 'В очереди'
  if (status.status === 'running') return status.mode === 'test' ? 'Тестовый парсинг идёт' : 'Полный парсинг идёт'
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
