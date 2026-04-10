import { ExternalLink, Mail, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { PurchaseStatusBadge } from '../purchases/PurchaseStatusBadge'
import {
  deleteAdminPurchase,
  fetchAdminPurchase,
  fetchAdminPurchases,
  fulfillAdminPurchase,
  updateAdminPurchase,
} from '../../services/admin'
import type {
  AdminPurchase,
  AdminPurchaseFulfillPayload,
  AdminPurchaseUpdatePayload,
} from '../../types/admin'
import type { PurchaseDeliveryItem } from '../../types/purchase'
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

type PurchaseEditorState = {
  status: AdminPurchase['status']
  status_note: string
  manager_contact_url: string
  payment_url: string
  delivery_title: string
  delivery_message: string
  delivery_items: PurchaseDeliveryItem[]
  send_email: boolean
}

const EMPTY_EDITOR: PurchaseEditorState = {
  status: 'payment_pending',
  status_note: '',
  manager_contact_url: '',
  payment_url: '',
  delivery_title: '',
  delivery_message: '',
  delivery_items: [{ label: '', value: '' }],
  send_email: true,
}

function fromOrder(order?: AdminPurchase | null): PurchaseEditorState {
  if (!order) {
    return EMPTY_EDITOR
  }

  return {
    status: order.status,
    status_note: order.status_note ?? '',
    manager_contact_url: order.manager_contact_url ?? '',
    payment_url: order.payment_url ?? '',
    delivery_title: order.delivery?.title ?? '',
    delivery_message: order.delivery?.message ?? '',
    delivery_items: order.delivery?.items?.length ? order.delivery.items : [{ label: '', value: '' }],
    send_email: true,
  }
}

export function AdminPurchasesSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [orders, setOrders] = useState<AdminPurchase[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(12)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [selectedOrder, setSelectedOrder] = useState<AdminPurchase | null>(null)
  const [editor, setEditor] = useState<PurchaseEditorState>(EMPTY_EDITOR)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isFulfilling, setIsFulfilling] = useState(false)

  async function loadOrders() {
    setIsLoading(true)
    try {
      const response = await fetchAdminPurchases({
        page,
        limit,
        search: search.trim() || undefined,
        status: statusFilter || undefined,
      })
      setOrders(response.orders)
      setTotal(response.total)
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить покупки.'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadOrders()
  }, [page, limit, search, statusFilter])

  async function startEdit(order: AdminPurchase) {
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const fullOrder = await fetchAdminPurchase(order.order_number)
      setSelectedOrder(fullOrder)
      setEditor(fromOrder(fullOrder))
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить заказ.'),
      })
    }
  }

  function updateDeliveryItem(index: number, patch: Partial<PurchaseDeliveryItem>) {
    setEditor((current) => ({
      ...current,
      delivery_items: current.delivery_items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }))
  }

  function addDeliveryItem() {
    setEditor((current) => ({
      ...current,
      delivery_items: [...current.delivery_items, { label: '', value: '' }],
    }))
  }

  function removeDeliveryItem(index: number) {
    setEditor((current) => ({
      ...current,
      delivery_items:
        current.delivery_items.length > 1
          ? current.delivery_items.filter((_, itemIndex) => itemIndex !== index)
          : [{ label: '', value: '' }],
    }))
  }

  async function handleSaveStatus() {
    if (!selectedOrder) {
      return
    }

    setIsSaving(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    const payload: AdminPurchaseUpdatePayload = {
      status: editor.status,
      status_note: editor.status_note.trim() || null,
      manager_contact_url: editor.manager_contact_url.trim() || null,
      payment_url: editor.payment_url.trim() || null,
    }

    try {
      const updatedOrder = await updateAdminPurchase(selectedOrder.order_number, payload)
      setSelectedOrder(updatedOrder)
      setEditor((current) => ({ ...current, ...fromOrder(updatedOrder) }))
      setNotice({ type: 'success', message: 'Заказ обновлён.' })
      await onDataChanged()
      await loadOrders()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось обновить заказ.'),
      })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleFulfill() {
    if (!selectedOrder) {
      return
    }

    setIsFulfilling(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    const payload: AdminPurchaseFulfillPayload = {
      delivery_title: editor.delivery_title.trim() || null,
      delivery_message: editor.delivery_message.trim() || null,
      delivery_items: editor.delivery_items
        .map((item) => ({
          label: item.label.trim(),
          value: item.value.trim(),
        }))
        .filter((item) => item.label && item.value),
      status_note: editor.status_note.trim() || null,
      send_email: editor.send_email,
    }

    try {
      const fulfilledOrder = await fulfillAdminPurchase(selectedOrder.order_number, payload)
      setSelectedOrder(fulfilledOrder)
      setEditor(fromOrder(fulfilledOrder))
      setNotice({ type: 'success', message: 'Заказ выдан и обновлён.' })
      await onDataChanged()
      await loadOrders()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось выдать заказ.'),
      })
    } finally {
      setIsFulfilling(false)
    }
  }

  async function handleDelete() {
    if (!selectedOrder) {
      return
    }

    if (!window.confirm(`Удалить заказ ${selectedOrder.order_number}?`)) {
      return
    }

    setIsDeleting(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      await deleteAdminPurchase(selectedOrder.order_number)
      setSelectedOrder(null)
      setEditor(EMPTY_EDITOR)
      setNotice({ type: 'success', message: 'Заказ удалён.' })
      await onDataChanged()
      await loadOrders()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось удалить заказ.'),
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const totalPages = Math.max(Math.ceil(total / limit), 1)

  return (
    <AdminSectionCard
      id="admin-purchases"
      title="Покупки и выдача"
      description="Отслеживание статусов, ручная выдача товара, отправка письма и управление заказами сайта."
      action={
        <button type="button" className="btn-secondary" onClick={() => loadOrders()}>
          <RefreshCw size={16} />
          Обновить
        </button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.95fr)] 2xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
        <div className="min-w-0 space-y-5">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
            <input
              value={search}
              onChange={(event) => {
                setPage(1)
                setSearch(event.target.value)
              }}
              className="auth-input"
              placeholder="Поиск по номеру, email или названию товара"
            />

            <select
              value={statusFilter}
              onChange={(event) => {
                setPage(1)
                setStatusFilter(event.target.value)
              }}
              className="auth-input"
            >
              <option value="">Все статусы</option>
              <option value="payment_pending">Ожидает оплату</option>
              <option value="payment_review">На проверке</option>
              <option value="fulfilled">Выдан</option>
              <option value="cancelled">Отменён</option>
            </select>
          </div>

          <AdminNotice state={notice} />

          <AdminTableShell>
            <div className="hidden grid-cols-[minmax(0,1.35fr)_140px_160px_140px_120px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
              <span>Заказ</span>
              <span>Покупатель</span>
              <span>Статус</span>
              <span>Сумма</span>
              <span>Действия</span>
            </div>

            {isLoading ? (
              <div className="space-y-3 px-5 py-5">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="h-20 animate-pulse rounded-[20px] bg-white/[0.04]" />
                ))}
              </div>
            ) : orders.length ? (
              <div className="divide-y divide-white/6">
                {orders.map((order) => (
                  <div key={order.order_number} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1.35fr)_140px_160px_140px_120px] lg:items-center">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">{order.product_name}</p>
                      <p className="mt-1 truncate text-sm text-slate-400">{order.order_number}</p>
                      <p className="mt-1 text-xs text-slate-500">{formatDateTime(order.created_at)}</p>
                    </div>

                    <div className="min-w-0 text-sm text-slate-300">
                      <p className="truncate">{order.user_email || order.user_display_name || 'Без email'}</p>
                      <p className="mt-1 text-xs text-slate-500">{order.product_region}</p>
                    </div>

                    <div>
                      <PurchaseStatusBadge status={order.status} label={order.status_label} />
                    </div>

                    <div className="text-sm text-slate-300">{formatRub(order.price_rub)} ₽</div>

                    <div className="flex gap-2">
                      <button type="button" className="btn-secondary px-4 py-2 text-xs" onClick={() => startEdit(order)}>
                        <Pencil size={14} />
                        Открыть
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8">
                <AdminEmptyState title="Покупок нет" description="Когда появятся заказы, здесь будет их лента со статусами и выдачей." />
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
              <button type="button" className="btn-secondary" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(current + 1, totalPages))}>
                Вперёд
              </button>
            </div>
          </div>
        </div>

        <div className="panel-soft min-w-0 rounded-[30px] p-4 sm:p-5 xl:p-6">
          <div className="border-b border-white/8 pb-4">
            <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Редактор заказа</p>
            <h3 className="mt-2 text-xl text-white">
              {selectedOrder ? selectedOrder.order_number : 'Выберите заказ слева'}
            </h3>
            {selectedOrder ? (
              <p className="mt-2 text-sm text-slate-400">
                {selectedOrder.product_name} • {selectedOrder.user_email || selectedOrder.user_display_name || 'Без email'}
              </p>
            ) : null}
          </div>

          {selectedOrder ? (
            <div className="mt-5 space-y-5">
              <div className="flex flex-wrap gap-3">
                <PurchaseStatusBadge status={selectedOrder.status} label={selectedOrder.status_label} />
                {selectedOrder.payment_url ? (
                  <a href={selectedOrder.payment_url} target="_blank" rel="noreferrer" className="btn-secondary">
                    <ExternalLink size={16} />
                    Платёжка
                  </a>
                ) : null}
                {selectedOrder.payment_email ? (
                  <span className="pill bg-white/5 text-slate-200">
                    <Mail size={14} />
                    {selectedOrder.payment_email}
                  </span>
                ) : null}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Статус</label>
                  <select
                    value={editor.status}
                    onChange={(event) => setEditor((current) => ({ ...current, status: event.target.value as PurchaseEditorState['status'] }))}
                    className="auth-input"
                  >
                    <option value="payment_pending">Ожидает оплату</option>
                    <option value="payment_review">На проверке</option>
                    <option value="fulfilled">Выдан</option>
                    <option value="cancelled">Отменён</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Менеджер</label>
                  <input
                    value={editor.manager_contact_url}
                    onChange={(event) => setEditor((current) => ({ ...current, manager_contact_url: event.target.value }))}
                    className="auth-input"
                    placeholder="https://t.me/..."
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-slate-200">Ссылка на оплату</label>
                  <input
                    value={editor.payment_url}
                    onChange={(event) => setEditor((current) => ({ ...current, payment_url: event.target.value }))}
                    className="auth-input"
                    placeholder="Платёжная ссылка"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-slate-200">Статус note</label>
                  <textarea
                    value={editor.status_note}
                    onChange={(event) => setEditor((current) => ({ ...current, status_note: event.target.value }))}
                    className="auth-input min-h-[110px] rounded-[24px]"
                    placeholder="Комментарий для пользователя или команды"
                  />
                </div>
              </div>

              <div className="rounded-[24px] border border-white/10 bg-slate-950/35 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-lg font-semibold text-white">Выдача товара</p>
                    <p className="mt-1 text-sm text-slate-400">Подготовь данные и отправь письмо после выдачи.</p>
                  </div>
                  <button type="button" className="btn-secondary" onClick={addDeliveryItem}>
                    <Plus size={16} />
                    Поле
                  </button>
                </div>

                <div className="mt-4 grid gap-4">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">Заголовок</label>
                    <input
                      value={editor.delivery_title}
                      onChange={(event) => setEditor((current) => ({ ...current, delivery_title: event.target.value }))}
                      className="auth-input"
                      placeholder="Данные по заказу"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">Сообщение</label>
                    <textarea
                      value={editor.delivery_message}
                      onChange={(event) => setEditor((current) => ({ ...current, delivery_message: event.target.value }))}
                      className="auth-input min-h-[110px] rounded-[24px]"
                      placeholder="Текст выдачи, инструкция, комментарий"
                    />
                  </div>

                  <div className="space-y-3">
                    {editor.delivery_items.map((item, index) => (
                      <div key={index} className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                        <div className="grid gap-3 md:grid-cols-[200px_minmax(0,1fr)_90px]">
                          <input
                            value={item.label}
                            onChange={(event) => updateDeliveryItem(index, { label: event.target.value })}
                            className="auth-input"
                            placeholder="Логин / Пароль / Код"
                          />
                          <input
                            value={item.value}
                            onChange={(event) => updateDeliveryItem(index, { value: event.target.value })}
                            className="auth-input"
                            placeholder="Значение"
                          />
                          <button type="button" className="btn-secondary" onClick={() => removeDeliveryItem(index)}>
                            Убрать
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <label className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-200">
                    <input
                      type="checkbox"
                      checked={editor.send_email}
                      onChange={(event) => setEditor((current) => ({ ...current, send_email: event.target.checked }))}
                    />
                    Отправить письмо после выдачи
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn-primary" onClick={handleSaveStatus} disabled={isSaving}>
                  {isSaving ? 'Сохраняем...' : 'Сохранить статус'}
                </button>
                <button type="button" className="btn-secondary" onClick={handleFulfill} disabled={isFulfilling}>
                  {isFulfilling ? 'Выдаём...' : 'Выдать заказ'}
                </button>
                <button type="button" className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10" onClick={handleDelete} disabled={isDeleting}>
                  <Trash2 size={16} />
                  {isDeleting ? 'Удаляем...' : 'Удалить'}
                </button>
              </div>

              <div className="rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-4 text-sm leading-7 text-slate-400">
                <p>Создан: {formatDateTime(selectedOrder.created_at)}</p>
                <p>Платёж провайдер: {selectedOrder.payment_provider}</p>
                <p>Сумма: {formatRub(selectedOrder.price_rub)} ₽</p>
              </div>
            </div>
          ) : (
            <div className="mt-5">
              <AdminEmptyState title="Заказ не выбран" description="Открой любой заказ слева, чтобы редактировать статус, оплату и выдачу." />
            </div>
          )}
        </div>
      </div>
    </AdminSectionCard>
  )
}
