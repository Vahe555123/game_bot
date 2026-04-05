import { BarChart3, Box, ShoppingBag, Users } from 'lucide-react'
import type { AdminDashboard } from '../../types/admin'
import { AdminEmptyState, AdminMetricCard, AdminSectionCard, AdminTableShell, formatDateTime, formatRub } from './AdminCommon'

const STATUS_LABELS: Record<string, string> = {
  payment_pending: 'Ожидают оплату',
  payment_review: 'На проверке',
  fulfilled: 'Выданы',
  cancelled: 'Отменены',
}

const REGION_LABELS: Record<string, string> = {
  TR: 'Турция',
  UA: 'Украина',
  IN: 'Индия',
}

export function AdminDashboardSection({
  dashboard,
  isLoading,
}: {
  dashboard: AdminDashboard | null
  isLoading: boolean
}) {
  if (isLoading && !dashboard) {
    return (
      <AdminSectionCard id="admin-dashboard" title="Дашборд" description="Собираем сводку по сайту.">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="panel-soft h-36 animate-pulse rounded-[26px]" />
          ))}
        </div>
      </AdminSectionCard>
    )
  }

  if (!dashboard) {
    return (
      <AdminSectionCard id="admin-dashboard" title="Дашборд">
        <AdminEmptyState title="Данные недоступны" description="Не удалось загрузить сводку админки." />
      </AdminSectionCard>
    )
  }

  return (
    <AdminSectionCard
      id="admin-dashboard"
      title="Дашборд"
      description="Быстрый срез по пользователям, каталогу и покупкам сайта."
      action={
        <div className="pill border-brand-300/20 bg-brand-500/10 text-brand-50">
          <BarChart3 size={14} />
          Обновляется по текущим данным
        </div>
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <AdminMetricCard
          label="Пользователи"
          value={dashboard.users.total}
          hint={`Администраторов: ${dashboard.users.admins} • Активных: ${dashboard.users.active}`}
        />
        <AdminMetricCard
          label="Каталог"
          value={dashboard.products.unique_products}
          hint={`Строк по регионам: ${dashboard.products.total_rows} • Со скидкой: ${dashboard.products.discounted}`}
        />
        <AdminMetricCard
          label="Покупки"
          value={dashboard.purchases.total}
          hint={`Выданы: ${dashboard.purchases.statuses.fulfilled ?? 0} • На проверке: ${dashboard.purchases.statuses.payment_review ?? 0}`}
        />
        <AdminMetricCard
          label="Оборот"
          value={`${formatRub(dashboard.purchases.total_revenue_rub)} ₽`}
          hint={`Выдано на ${formatRub(dashboard.purchases.fulfilled_revenue_rub)} ₽`}
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="space-y-6">
          <AdminTableShell>
            <div className="border-b border-white/8 px-5 py-4">
              <div className="flex items-center gap-2 text-white">
                <Users size={16} className="text-brand-200" />
                <span className="text-sm font-semibold uppercase tracking-[0.24em]">Пользователи</span>
              </div>
            </div>

            <div className="grid gap-3 px-5 py-5 sm:grid-cols-2 xl:grid-cols-5">
              <AdminMetricCard label="Всего" value={dashboard.users.total} />
              <AdminMetricCard label="Активные" value={dashboard.users.active} />
              <AdminMetricCard label="Подтверждённые" value={dashboard.users.verified} />
              <AdminMetricCard label="Админы" value={dashboard.users.admins} />
              <AdminMetricCard label="Клиенты" value={dashboard.users.clients} />
            </div>
          </AdminTableShell>

          <AdminTableShell>
            <div className="border-b border-white/8 px-5 py-4">
              <div className="flex items-center gap-2 text-white">
                <Box size={16} className="text-brand-200" />
                <span className="text-sm font-semibold uppercase tracking-[0.24em]">Каталог</span>
              </div>
            </div>

            <div className="grid gap-3 px-5 py-5 sm:grid-cols-2 xl:grid-cols-4">
              <AdminMetricCard label="Уникальные товары" value={dashboard.products.unique_products} />
              <AdminMetricCard label="Строки каталога" value={dashboard.products.total_rows} />
              <AdminMetricCard label="Со скидкой" value={dashboard.products.discounted} />
              <AdminMetricCard label="PS Plus" value={dashboard.products.with_ps_plus} />
            </div>

            <div className="border-t border-white/8 px-5 py-5">
              <p className="text-sm font-semibold text-white">По регионам</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(dashboard.products.regions).map(([region, count]) => (
                  <span key={region} className="pill bg-white/5 text-slate-200">
                    {REGION_LABELS[region] || region}: {count}
                  </span>
                ))}
              </div>
            </div>
          </AdminTableShell>
        </div>

        <div className="space-y-6">
          <AdminTableShell>
            <div className="border-b border-white/8 px-5 py-4">
              <div className="flex items-center gap-2 text-white">
                <ShoppingBag size={16} className="text-brand-200" />
                <span className="text-sm font-semibold uppercase tracking-[0.24em]">Последние покупки</span>
              </div>
            </div>

            {dashboard.recent_orders.length ? (
              <div className="divide-y divide-white/6">
                {dashboard.recent_orders.map((order) => (
                  <div key={order.order_number} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-semibold text-white">{order.product_name}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.24em] text-slate-500">{order.order_number}</p>
                      </div>
                      <span className="pill bg-white/5 text-slate-200">
                        {STATUS_LABELS[order.status] || order.status_label}
                      </span>
                    </div>
                    <p className="mt-3 text-sm text-slate-400">
                      {order.user_email || order.user_display_name || 'Без email'} • {formatRub(order.price_rub)} ₽
                    </p>
                    <p className="mt-1 text-xs text-slate-500">{formatDateTime(order.created_at)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8">
                <AdminEmptyState title="Покупок пока нет" description="Как только появятся заказы, они будут видны здесь." />
              </div>
            )}
          </AdminTableShell>

          <AdminTableShell>
            <div className="border-b border-white/8 px-5 py-4">
              <div className="flex items-center gap-2 text-white">
                <Users size={16} className="text-brand-200" />
                <span className="text-sm font-semibold uppercase tracking-[0.24em]">Последние пользователи</span>
              </div>
            </div>

            {dashboard.recent_users.length ? (
              <div className="divide-y divide-white/6">
                {dashboard.recent_users.map((user) => (
                  <div key={user.id} className="px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {[user.first_name, user.last_name].filter(Boolean).join(' ').trim() || user.username || user.email || 'Пользователь'}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">{user.email || (user.telegram_id ? `Telegram: ${user.telegram_id}` : 'Без email')}</p>
                      </div>
                      <span className={`pill ${user.is_admin ? 'border-brand-300/20 bg-brand-500/10 text-brand-50' : 'bg-white/5 text-slate-200'}`}>
                        {user.is_admin ? 'Админ' : 'Клиент'}
                      </span>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">
                      Покупок: {user.purchase_count} • Потрачено: {formatRub(user.total_spent_rub)} ₽
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8">
                <AdminEmptyState title="Пользователей пока нет" description="Новые аккаунты появятся здесь автоматически." />
              </div>
            )}
          </AdminTableShell>
        </div>
      </div>
    </AdminSectionCard>
  )
}
