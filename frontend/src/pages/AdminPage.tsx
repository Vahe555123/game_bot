import { BadgePercent, Database, FileText, Globe, LayoutDashboard, LinkIcon, Package2, PanelLeftClose, PanelLeftOpen, RefreshCw, Shield, ShoppingBag, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AdminContentSection } from '../components/admin/AdminContentSection'
import { AdminDashboardSection } from '../components/admin/AdminDashboardSection'
import { AdminDiscountsSection } from '../components/admin/AdminDiscountsSection'
import { AdminFullParseSection } from '../components/admin/AdminFullParseSection'
import { AdminPricesSection } from '../components/admin/AdminPricesSection'
import { AdminProductsSection } from '../components/admin/AdminProductsSection'
import { AdminProxiesSection } from '../components/admin/AdminProxiesSection'
import { AdminPurchasesSection } from '../components/admin/AdminPurchasesSection'
import { AdminUnparsedSection } from '../components/admin/AdminUnparsedSection'
import { AdminUsersSection } from '../components/admin/AdminUsersSection'
import { useAuth } from '../context/AuthContext'
import { fetchAdminDashboard } from '../services/admin'
import type { AdminDashboard } from '../types/admin'
import { getApiErrorMessage } from '../utils/apiErrors'

const SECTIONS = [
  { id: 'admin-dashboard', label: 'Дашборд', icon: LayoutDashboard },
  { id: 'admin-products', label: 'Товары', icon: Package2 },
  { id: 'admin-discounts', label: 'Скидки', icon: BadgePercent },
  { id: 'admin-prices', label: 'Обновление цен', icon: RefreshCw },
  { id: 'admin-full-parse', label: 'Полный парсинг', icon: Database },
  { id: 'admin-proxies', label: 'Прокси', icon: Globe },
  { id: 'admin-unparsed', label: 'Не спарсенные URL', icon: LinkIcon },
  { id: 'admin-purchases', label: 'Покупки', icon: ShoppingBag },
  { id: 'admin-content', label: 'Помощь', icon: FileText },
  { id: 'admin-users', label: 'Пользователи', icon: Users },
] as const

const ADMIN_SIDEBAR_KEY = 'admin:sidebar:open'

export function AdminPage() {
  const { user } = useAuth()
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null)
  const [isDashboardLoading, setIsDashboardLoading] = useState(true)
  const [dashboardError, setDashboardError] = useState<string | null>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window === 'undefined') return true
    const stored = window.localStorage.getItem(ADMIN_SIDEBAR_KEY)
    return stored === null ? true : stored === '1'
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(ADMIN_SIDEBAR_KEY, isSidebarOpen ? '1' : '0')
    }
  }, [isSidebarOpen])

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

  const sidebarGridClass = isSidebarOpen
    ? 'grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)] 2xl:grid-cols-[280px_minmax(0,1fr)]'
    : 'grid gap-6 xl:grid-cols-[minmax(0,1fr)]'

  return (
    <div className="relative w-full px-3 py-6 sm:px-4 md:px-6 md:py-8 xl:px-8 xl:py-10 2xl:px-10">
      <button
        type="button"
        onClick={() => setIsSidebarOpen((value) => !value)}
        className="hidden xl:inline-flex items-center gap-2 fixed left-4 top-28 z-30 rounded-full border border-white/10 bg-slate-950/80 px-4 py-2 text-xs font-semibold text-slate-200 shadow-card backdrop-blur-lg transition hover:border-brand-300/40 hover:bg-brand-500/10"
        title={isSidebarOpen ? 'Скрыть боковую панель' : 'Показать боковую панель'}
        aria-pressed={isSidebarOpen}
      >
        {isSidebarOpen ? <PanelLeftClose size={14} /> : <PanelLeftOpen size={14} />}
        <span>{isSidebarOpen ? 'Скрыть меню' : 'Меню'}</span>
      </button>

      <div className={sidebarGridClass}>
        {isSidebarOpen ? (
          <aside className="xl:sticky xl:top-24 xl:self-start">
            <div className="panel-soft rounded-[30px] p-3 sm:p-4">
              <div className="mb-2 flex items-center justify-between px-2 xl:hidden">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Разделы</p>
                <button
                  type="button"
                  onClick={() => setIsSidebarOpen(false)}
                  className="rounded-full border border-white/10 bg-white/[0.04] p-1.5 text-slate-300 hover:text-white"
                  aria-label="Скрыть меню"
                >
                  <PanelLeftClose size={14} />
                </button>
              </div>
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
        ) : null}

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
          <AdminDiscountsSection onDataChanged={loadDashboard} />
          <AdminPricesSection onDataChanged={loadDashboard} />
          <AdminFullParseSection onDataChanged={loadDashboard} />
          <AdminProxiesSection />
          <AdminUnparsedSection />
          <AdminPurchasesSection onDataChanged={loadDashboard} />
          <AdminContentSection />
          <AdminUsersSection onDataChanged={loadDashboard} />
        </div>
      </div>
    </div>
  )
}
