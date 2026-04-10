import { FileText, LayoutDashboard, Package2, Shield, ShoppingBag, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AdminContentSection } from '../components/admin/AdminContentSection'
import { AdminDashboardSection } from '../components/admin/AdminDashboardSection'
import { AdminProductsSection } from '../components/admin/AdminProductsSection'
import { AdminPurchasesSection } from '../components/admin/AdminPurchasesSection'
import { AdminUsersSection } from '../components/admin/AdminUsersSection'
import { useAuth } from '../context/AuthContext'
import { fetchAdminDashboard } from '../services/admin'
import type { AdminDashboard } from '../types/admin'
import { getApiErrorMessage } from '../utils/apiErrors'

const SECTIONS = [
  { id: 'admin-dashboard', label: 'Дашборд', icon: LayoutDashboard },
  { id: 'admin-products', label: 'Товары', icon: Package2 },
  { id: 'admin-purchases', label: 'Покупки', icon: ShoppingBag },
  { id: 'admin-content', label: 'Помощь', icon: FileText },
  { id: 'admin-users', label: 'Пользователи', icon: Users },
] as const

export function AdminPage() {
  const { user } = useAuth()
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null)
  const [isDashboardLoading, setIsDashboardLoading] = useState(true)
  const [dashboardError, setDashboardError] = useState<string | null>(null)

  async function loadDashboard() {
    setIsDashboardLoading(true)
    setDashboardError(null)

    try {
      const response = await fetchAdminDashboard()
      setDashboard(response)
    } catch (error) {
      setDashboardError(getApiErrorMessage(error, 'Не удалось загрузить данные админки.'))
    } finally {
      setIsDashboardLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim() ||
    user?.username ||
    user?.email ||
    'Администратор'

  return (
    <div className="mx-auto w-full max-w-[1880px] px-3 py-6 sm:px-4 md:px-6 md:py-8 xl:px-8 xl:py-10 2xl:px-10">
      <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)] 2xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="xl:sticky xl:top-24 xl:self-start">
          <div className="panel-soft rounded-[30px] p-3 sm:p-4">
            <div className="flex gap-2 overflow-x-auto pb-1 xl:grid xl:gap-2 xl:overflow-visible xl:pb-0">
              {SECTIONS.map(({ id, label, icon: Icon }) => (
                <a
                  key={id}
                  href={`#${id}`}
                  className="flex min-w-[180px] items-center gap-3 rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-brand-300/40 hover:bg-brand-500/10 xl:min-w-0"
                >
                  <Icon size={16} className="shrink-0 text-brand-200" />
                  <span className="truncate">{label}</span>
                </a>
              ))}
            </div>
          </div>
        </aside>

        <div className="min-w-0 space-y-6">
          <section className="panel mesh-bg overflow-hidden rounded-[34px] p-6 md:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="pill border-brand-300/20 bg-brand-500/10 text-brand-50">
                  <Shield size={14} />
                  Site Admin Control
                </div>
                <h1 className="mt-5 max-w-3xl text-4xl leading-tight text-white md:text-5xl">
                  Полная админка сайта: контент, пользователи, каталог, покупки и дашборд.
                </h1>
                <p className="mt-4 max-w-3xl text-sm leading-8 text-slate-300">
                  Здесь собран отдельный web-admin слой поверх текущего FastAPI backend: контент страниц, роли,
                  управление пользователями, каталогом, покупками и общей сводкой по проекту.
                </p>
              </div>

              <div className="rounded-[28px] border border-white/10 bg-slate-950/35 px-5 py-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Текущий админ</p>
                <p className="mt-2 text-lg font-semibold text-white">{displayName}</p>
                <p className="mt-1 text-sm text-slate-400">
                  {user?.email || (user?.telegram_id ? `Telegram ${user.telegram_id}` : 'Без email')}
                </p>
              </div>
            </div>

            {dashboardError ? (
              <div className="mt-6 rounded-[24px] border border-rose-400/20 bg-rose-500/10 px-5 py-4 text-sm text-rose-50">
                {dashboardError}
              </div>
            ) : null}
          </section>

          <AdminDashboardSection dashboard={dashboard} isLoading={isDashboardLoading} />
          <AdminProductsSection onDataChanged={loadDashboard} />
          <AdminPurchasesSection onDataChanged={loadDashboard} />
          <AdminContentSection />
          <AdminUsersSection onDataChanged={loadDashboard} />
        </div>
      </div>
    </div>
  )
}
