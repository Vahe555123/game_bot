import { type ReactNode } from 'react'

export type AdminNoticeState = {
  type: 'idle' | 'info' | 'success' | 'error'
  message: string | null
}

export const EMPTY_ADMIN_NOTICE: AdminNoticeState = {
  type: 'idle',
  message: null,
}

export function AdminSectionCard({
  id,
  title,
  description,
  action,
  children,
}: {
  id?: string
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section id={id} className="panel-soft rounded-[30px] p-5 sm:p-6 xl:p-7">
      <div className="flex flex-col gap-4 border-b border-white/8 pb-5 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h2 className="text-2xl text-white">{title}</h2>
          {description ? <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">{description}</p> : null}
        </div>
        {action}
      </div>

      <div className="pt-5">{children}</div>
    </section>
  )
}

export function AdminNotice({ state }: { state: AdminNoticeState }) {
  if (!state.message || state.type === 'idle') {
    return null
  }

  const className =
    state.type === 'error'
      ? 'auth-alert auth-alert-error'
      : state.type === 'success'
        ? 'auth-alert border-emerald-400/20 bg-emerald-500/10 text-emerald-50'
        : 'auth-alert auth-alert-info'

  return <div className={className}>{state.message}</div>
}

export function AdminMetricCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <article className="rounded-[26px] border border-white/10 bg-slate-950/45 p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-2 text-sm text-slate-500">{hint}</p> : null}
    </article>
  )
}

export function AdminTableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[26px] border border-white/10 bg-slate-950/45">
      <div className="overflow-x-auto">{children}</div>
    </div>
  )
}

export function AdminEmptyState({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="rounded-[24px] border border-dashed border-white/10 bg-white/[0.03] px-5 py-8 text-center">
      <p className="text-base font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm leading-7 text-slate-400">{description}</p>
    </div>
  )
}

export function formatRub(value: number) {
  return new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatDateTime(value?: string | null) {
  if (!value) {
    return '—'
  }

  return new Date(value).toLocaleString('ru-RU')
}
