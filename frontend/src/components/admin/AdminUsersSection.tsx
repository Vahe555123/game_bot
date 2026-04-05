import { Pencil, Plus, RefreshCw, Shield, Trash2, UserPlus } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  createAdminUser,
  deleteAdminUser,
  fetchAdminUsers,
  updateAdminUser,
} from '../../services/admin'
import type { AdminUser, AdminUserPayload } from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import {
  AdminEmptyState,
  AdminNotice,
  AdminSectionCard,
  AdminTableShell,
  EMPTY_ADMIN_NOTICE,
  formatDateTime,
  formatRub,
  type AdminNoticeState,
} from './AdminCommon'

type UserFormState = {
  email: string
  password: string
  email_verified: boolean
  username: string
  first_name: string
  last_name: string
  telegram_id: string
  preferred_region: 'TR' | 'UA' | 'IN'
  payment_email: string
  platform: '' | 'PS4' | 'PS5'
  psn_email: string
  role: 'client' | 'admin'
  is_active: boolean
}

const EMPTY_FORM: UserFormState = {
  email: '',
  password: '',
  email_verified: false,
  username: '',
  first_name: '',
  last_name: '',
  telegram_id: '',
  preferred_region: 'TR',
  payment_email: '',
  platform: '',
  psn_email: '',
  role: 'client',
  is_active: true,
}

function buildFormState(user?: AdminUser | null): UserFormState {
  if (!user) {
    return EMPTY_FORM
  }

  const preferredRegion =
    user.preferred_region === 'UA' || user.preferred_region === 'TR' || user.preferred_region === 'IN'
      ? user.preferred_region
      : 'TR'
  const platform = user.platform === 'PS4' || user.platform === 'PS5' ? user.platform : ''

  return {
    email: user.email ?? '',
    password: '',
    email_verified: user.email_verified,
    username: user.username ?? '',
    first_name: user.first_name ?? '',
    last_name: user.last_name ?? '',
    telegram_id: user.telegram_id ? String(user.telegram_id) : '',
    preferred_region: preferredRegion,
    payment_email: user.payment_email ?? '',
    platform,
    psn_email: user.psn_email ?? '',
    role: user.role,
    is_active: user.is_active,
  }
}

function toPayload(form: UserFormState): AdminUserPayload {
  return {
    email: form.email.trim() || null,
    password: form.password.trim() || null,
    email_verified: form.email_verified,
    username: form.username.trim() || null,
    first_name: form.first_name.trim() || null,
    last_name: form.last_name.trim() || null,
    telegram_id: form.telegram_id.trim() ? Number(form.telegram_id.trim()) : null,
    preferred_region: form.preferred_region,
    payment_email: form.payment_email.trim() || null,
    platform: form.platform || null,
    psn_email: form.psn_email.trim() || null,
    role: form.role,
    is_active: form.is_active,
  }
}

export function AdminUsersSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(12)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)
  const [form, setForm] = useState<UserFormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  async function loadUsers() {
    setIsLoading(true)
    try {
      const response = await fetchAdminUsers({
        page,
        limit,
        search: search.trim() || undefined,
        role: roleFilter || undefined,
        is_active:
          statusFilter === 'active' ? true : statusFilter === 'inactive' ? false : undefined,
      })
      setUsers(response.users)
      setTotal(response.total)
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить пользователей.'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [page, limit, roleFilter, search, statusFilter])

  function startCreate() {
    setSelectedUser(null)
    setForm(EMPTY_FORM)
    setNotice(EMPTY_ADMIN_NOTICE)
  }

  function startEdit(user: AdminUser) {
    setSelectedUser(user)
    setForm(buildFormState(user))
    setNotice(EMPTY_ADMIN_NOTICE)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSaving(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      if (selectedUser) {
        const updatedUser = await updateAdminUser(selectedUser.id, toPayload(form))
        setUsers((current) => current.map((item) => (item.id === updatedUser.id ? updatedUser : item)))
        setSelectedUser(updatedUser)
        setForm(buildFormState(updatedUser))
        setNotice({ type: 'success', message: 'Пользователь обновлён.' })
      } else {
        const createdUser = await createAdminUser(toPayload(form))
        setUsers((current) => [createdUser, ...current])
        setSelectedUser(createdUser)
        setForm(buildFormState(createdUser))
        setNotice({ type: 'success', message: 'Пользователь создан.' })
      }
      await onDataChanged()
      await loadUsers()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось сохранить пользователя.'),
      })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!selectedUser) {
      return
    }

    if (!window.confirm(`Удалить пользователя ${selectedUser.email || selectedUser.username || selectedUser.id}?`)) {
      return
    }

    setIsDeleting(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      await deleteAdminUser(selectedUser.id)
      setUsers((current) => current.filter((item) => item.id !== selectedUser.id))
      setSelectedUser(null)
      setForm(EMPTY_FORM)
      setNotice({ type: 'success', message: 'Пользователь удалён.' })
      await onDataChanged()
      await loadUsers()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось удалить пользователя.'),
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const totalPages = Math.max(Math.ceil(total / limit), 1)

  return (
    <AdminSectionCard
      id="admin-users"
      title="Пользователи"
      description="Управление ролями, доступом, регионами и базовыми данными клиентов сайта."
      action={
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary" onClick={() => loadUsers()}>
            <RefreshCw size={16} />
            Обновить
          </button>
          <button type="button" className="btn-primary" onClick={startCreate}>
            <Plus size={16} />
            Новый пользователь
          </button>
        </div>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_180px]">
            <input
              value={search}
              onChange={(event) => {
                setPage(1)
                setSearch(event.target.value)
              }}
              className="auth-input"
              placeholder="Поиск по email, имени или Telegram ID"
            />

            <select
              value={roleFilter}
              onChange={(event) => {
                setPage(1)
                setRoleFilter(event.target.value)
              }}
              className="auth-input"
            >
              <option value="">Все роли</option>
              <option value="client">Клиенты</option>
              <option value="admin">Админы</option>
            </select>

            <select
              value={statusFilter}
              onChange={(event) => {
                setPage(1)
                setStatusFilter(event.target.value)
              }}
              className="auth-input"
            >
              <option value="">Любой статус</option>
              <option value="active">Активные</option>
              <option value="inactive">Отключённые</option>
            </select>
          </div>

          <AdminNotice state={notice} />

          <AdminTableShell>
            <div className="hidden grid-cols-[minmax(0,1.25fr)_120px_120px_110px_130px_120px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
              <span>Пользователь</span>
              <span>Роль</span>
              <span>Статус</span>
              <span>Регион</span>
              <span>Покупки</span>
              <span>Действия</span>
            </div>

            {isLoading ? (
              <div className="space-y-3 px-5 py-5">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="h-20 animate-pulse rounded-[20px] bg-white/[0.04]" />
                ))}
              </div>
            ) : users.length ? (
              <div className="divide-y divide-white/6">
                {users.map((user) => {
                  const displayName =
                    [user.first_name, user.last_name].filter(Boolean).join(' ').trim() ||
                    user.username ||
                    user.email ||
                    user.id

                  return (
                    <div key={user.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1.25fr)_120px_120px_110px_130px_120px] lg:items-center">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-white">{displayName}</p>
                        <p className="mt-1 truncate text-sm text-slate-400">
                          {user.email || (user.telegram_id ? `Telegram: ${user.telegram_id}` : 'Без email')}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">Создан: {formatDateTime(user.created_at)}</p>
                      </div>

                      <div>
                        <span
                          className={`pill ${
                            user.is_admin ? 'border-brand-300/20 bg-brand-500/10 text-brand-50' : 'bg-white/5 text-slate-200'
                          }`}
                        >
                          {user.is_admin ? 'Админ' : 'Клиент'}
                        </span>
                        {user.is_env_admin ? (
                          <span className="mt-2 inline-flex items-center gap-1 text-xs text-amber-200">
                            <Shield size={12} />
                            .env admin
                          </span>
                        ) : null}
                      </div>

                      <div>
                        <span className={`pill ${user.is_active ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-50' : 'bg-white/5 text-slate-300'}`}>
                          {user.is_active ? 'Активен' : 'Отключён'}
                        </span>
                      </div>

                      <div className="text-sm text-slate-300">{user.preferred_region}</div>

                      <div className="text-sm text-slate-300">
                        {user.purchase_count} • {formatRub(user.total_spent_rub)} ₽
                      </div>

                      <div className="flex gap-2">
                        <button type="button" className="btn-secondary px-4 py-2 text-xs" onClick={() => startEdit(user)}>
                          <Pencil size={14} />
                          Изменить
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="px-5 py-8">
                <AdminEmptyState title="Пользователи не найдены" description="Смените фильтры или создайте нового пользователя вручную." />
              </div>
            )}
          </AdminTableShell>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-400">
              Всего: {total} • Страница {page} из {totalPages}
            </p>
            <div className="flex gap-3">
              <button type="button" className="btn-secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(current - 1, 1))}>
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
        </div>

        <div className="panel-soft rounded-[30px] p-5">
          <div className="flex items-center justify-between gap-4 border-b border-white/8 pb-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Редактор</p>
              <h3 className="mt-2 text-xl text-white">
                {selectedUser ? 'Редактирование пользователя' : 'Создание пользователя'}
              </h3>
            </div>
            {!selectedUser ? (
              <div className="pill bg-white/5 text-slate-200">
                <UserPlus size={14} />
                Новый
              </div>
            ) : null}
          </div>

          <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Email</label>
                <input
                  value={form.email}
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                  className="auth-input"
                  placeholder="user@example.com"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Пароль</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  className="auth-input"
                  placeholder={selectedUser ? 'Оставьте пустым, чтобы не менять' : 'Минимум 8 символов'}
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Имя</label>
                <input
                  value={form.first_name}
                  onChange={(event) => setForm((current) => ({ ...current, first_name: event.target.value }))}
                  className="auth-input"
                  placeholder="Имя"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Фамилия</label>
                <input
                  value={form.last_name}
                  onChange={(event) => setForm((current) => ({ ...current, last_name: event.target.value }))}
                  className="auth-input"
                  placeholder="Фамилия"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Username</label>
                <input
                  value={form.username}
                  onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                  className="auth-input"
                  placeholder="@username"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Telegram ID</label>
                <input
                  value={form.telegram_id}
                  onChange={(event) => setForm((current) => ({ ...current, telegram_id: event.target.value.replace(/[^\d-]/g, '') }))}
                  className="auth-input"
                  placeholder="725505758"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Роль</label>
                <select
                  value={form.role}
                  onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as UserFormState['role'] }))}
                  className="auth-input"
                >
                  <option value="client">Клиент</option>
                  <option value="admin">Админ</option>
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Регион</label>
                <select
                  value={form.preferred_region}
                  onChange={(event) => setForm((current) => ({ ...current, preferred_region: event.target.value as UserFormState['preferred_region'] }))}
                  className="auth-input"
                >
                  <option value="TR">Турция</option>
                  <option value="UA">Украина</option>
                  <option value="IN">Индия</option>
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Email для покупки</label>
                <input
                  value={form.payment_email}
                  onChange={(event) => setForm((current) => ({ ...current, payment_email: event.target.value }))}
                  className="auth-input"
                  placeholder="checkout@example.com"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Платформа</label>
                <select
                  value={form.platform}
                  onChange={(event) => setForm((current) => ({ ...current, platform: event.target.value as UserFormState['platform'] }))}
                  className="auth-input"
                >
                  <option value="">Не указана</option>
                  <option value="PS5">PlayStation 5</option>
                  <option value="PS4">PlayStation 4</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="mb-2 block text-sm font-medium text-slate-200">PSN Email</label>
                <input
                  value={form.psn_email}
                  onChange={(event) => setForm((current) => ({ ...current, psn_email: event.target.value }))}
                  className="auth-input"
                  placeholder="psn@example.com"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={form.email_verified}
                  onChange={(event) => setForm((current) => ({ ...current, email_verified: event.target.checked }))}
                />
                Email подтверждён
              </label>

              <label className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
                />
                Аккаунт активен
              </label>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button type="submit" className="btn-primary" disabled={isSaving}>
                {isSaving ? 'Сохраняем...' : selectedUser ? 'Сохранить изменения' : 'Создать пользователя'}
              </button>

              <button type="button" className="btn-secondary" onClick={startCreate}>
                Очистить
              </button>

              {selectedUser ? (
                <button type="button" className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10" onClick={handleDelete} disabled={isDeleting}>
                  <Trash2 size={16} />
                  {isDeleting ? 'Удаляем...' : 'Удалить'}
                </button>
              ) : null}
            </div>

            {selectedUser ? (
              <div className="rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-4 text-sm leading-7 text-slate-400">
                <p>ID: {selectedUser.id}</p>
                <p>Последний вход: {formatDateTime(selectedUser.last_login_at)}</p>
                <p>Провайдеры: {selectedUser.auth_providers.length ? selectedUser.auth_providers.join(', ') : 'нет'}</p>
              </div>
            ) : null}
          </form>
        </div>
      </div>
    </AdminSectionCard>
  )
}
