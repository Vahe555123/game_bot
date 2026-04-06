import { Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  createAdminProduct,
  deleteAdminProduct,
  fetchAdminProduct,
  fetchAdminProducts,
  updateAdminProduct,
} from '../../services/admin'
import type { AdminProduct, AdminProductPayload, AdminProductSortMode } from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import {
  AdminEmptyState,
  AdminNotice,
  AdminSectionCard,
  AdminTableShell,
  EMPTY_ADMIN_NOTICE,
  type AdminNoticeState,
} from './AdminCommon'

type ProductFormState = {
  id: string
  region: 'TR' | 'UA' | 'IN'
  category: string
  type: string
  name: string
  main_name: string
  search_names: string
  image: string
  platforms: string
  publisher: string
  localization: string
  rating: string
  edition: string
  price: string
  old_price: string
  ps_price: string
  ea_price: string
  price_uah: string
  old_price_uah: string
  price_try: string
  old_price_try: string
  price_inr: string
  old_price_inr: string
  ps_plus_price_uah: string
  ps_plus_price_try: string
  ps_plus_price_inr: string
  plus_types: string
  ps_plus: boolean
  ea_access: string
  ps_plus_collection: string
  discount: string
  discount_end: string
  tags: string
  description: string
  compound: string
  info: string
  players_min: string
  players_max: string
  players_online: boolean
}

const EMPTY_FORM: ProductFormState = {
  id: '',
  region: 'TR',
  category: '',
  type: '',
  name: '',
  main_name: '',
  search_names: '',
  image: '',
  platforms: '',
  publisher: '',
  localization: '',
  rating: '',
  edition: '',
  price: '',
  old_price: '',
  ps_price: '',
  ea_price: '',
  price_uah: '',
  old_price_uah: '',
  price_try: '',
  old_price_try: '',
  price_inr: '',
  old_price_inr: '',
  ps_plus_price_uah: '',
  ps_plus_price_try: '',
  ps_plus_price_inr: '',
  plus_types: '',
  ps_plus: false,
  ea_access: '',
  ps_plus_collection: '',
  discount: '',
  discount_end: '',
  tags: '',
  description: '',
  compound: '',
  info: '',
  players_min: '',
  players_max: '',
  players_online: false,
}

function fromProduct(product?: AdminProduct | null): ProductFormState {
  if (!product) {
    return EMPTY_FORM
  }

  return {
    id: product.id,
    region: product.region,
    category: product.category ?? '',
    type: product.type ?? '',
    name: product.name ?? '',
    main_name: product.main_name ?? '',
    search_names: product.search_names ?? '',
    image: product.image ?? '',
    platforms: product.platforms ?? '',
    publisher: product.publisher ?? '',
    localization: product.localization ?? '',
    rating: product.rating != null ? String(product.rating) : '',
    edition: product.edition ?? '',
    price: product.price != null ? String(product.price) : '',
    old_price: product.old_price != null ? String(product.old_price) : '',
    ps_price: product.ps_price != null ? String(product.ps_price) : '',
    ea_price: product.ea_price != null ? String(product.ea_price) : '',
    price_uah: product.price_uah != null ? String(product.price_uah) : '',
    old_price_uah: product.old_price_uah != null ? String(product.old_price_uah) : '',
    price_try: product.price_try != null ? String(product.price_try) : '',
    old_price_try: product.old_price_try != null ? String(product.old_price_try) : '',
    price_inr: product.price_inr != null ? String(product.price_inr) : '',
    old_price_inr: product.old_price_inr != null ? String(product.old_price_inr) : '',
    ps_plus_price_uah: product.ps_plus_price_uah != null ? String(product.ps_plus_price_uah) : '',
    ps_plus_price_try: product.ps_plus_price_try != null ? String(product.ps_plus_price_try) : '',
    ps_plus_price_inr: product.ps_plus_price_inr != null ? String(product.ps_plus_price_inr) : '',
    plus_types: product.plus_types ?? '',
    ps_plus: product.ps_plus,
    ea_access: product.ea_access ?? '',
    ps_plus_collection: product.ps_plus_collection ?? '',
    discount: product.discount != null ? String(product.discount) : '',
    discount_end: product.discount_end ?? '',
    tags: product.tags ?? '',
    description: product.description ?? '',
    compound: product.compound ?? '',
    info: product.info ?? '',
    players_min: product.players_min != null ? String(product.players_min) : '',
    players_max: product.players_max != null ? String(product.players_max) : '',
    players_online: product.players_online,
  }
}

function parseNumber(value: string) {
  const normalized = value.trim().replace(',', '.')
  if (!normalized) {
    return null
  }
  const parsed = Number(normalized)
  return Number.isNaN(parsed) ? null : parsed
}

function toPayload(form: ProductFormState): AdminProductPayload {
  return {
    id: form.id.trim(),
    region: form.region,
    category: form.category.trim() || null,
    type: form.type.trim() || null,
    name: form.name.trim() || null,
    main_name: form.main_name.trim() || null,
    search_names: form.search_names.trim() || null,
    image: form.image.trim() || null,
    platforms: form.platforms.trim() || null,
    publisher: form.publisher.trim() || null,
    localization: form.localization.trim() || null,
    rating: parseNumber(form.rating),
    edition: form.edition.trim() || null,
    price: parseNumber(form.price),
    old_price: parseNumber(form.old_price),
    ps_price: parseNumber(form.ps_price),
    ea_price: parseNumber(form.ea_price),
    price_uah: parseNumber(form.price_uah),
    old_price_uah: parseNumber(form.old_price_uah),
    price_try: parseNumber(form.price_try),
    old_price_try: parseNumber(form.old_price_try),
    price_inr: parseNumber(form.price_inr),
    old_price_inr: parseNumber(form.old_price_inr),
    ps_plus_price_uah: parseNumber(form.ps_plus_price_uah),
    ps_plus_price_try: parseNumber(form.ps_plus_price_try),
    ps_plus_price_inr: parseNumber(form.ps_plus_price_inr),
    plus_types: form.plus_types.trim() || null,
    ps_plus: form.ps_plus,
    ea_access: form.ea_access.trim() || null,
    ps_plus_collection: form.ps_plus_collection.trim() || null,
    discount: parseNumber(form.discount),
    discount_end: form.discount_end.trim() || null,
    tags: form.tags.trim() || null,
    description: form.description.trim() || null,
    compound: form.compound.trim() || null,
    info: form.info.trim() || null,
    players_min: parseNumber(form.players_min),
    players_max: parseNumber(form.players_max),
    players_online: form.players_online,
  }
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  disabled = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  disabled?: boolean
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-200">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="auth-input"
        placeholder={placeholder}
        disabled={disabled}
      />
    </div>
  )
}

function TextAreaField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-200">{label}</label>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="auth-input min-h-[110px] rounded-[24px]"
        placeholder={placeholder}
      />
    </div>
  )
}

export function AdminProductsSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [products, setProducts] = useState<AdminProduct[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(12)
  const [search, setSearch] = useState('')
  const [regionFilter, setRegionFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [sort, setSort] = useState<AdminProductSortMode>('popular')
  const [isLoading, setIsLoading] = useState(true)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [selectedProduct, setSelectedProduct] = useState<AdminProduct | null>(null)
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  async function loadProducts() {
    setIsLoading(true)
    try {
      const response = await fetchAdminProducts({
        page,
        limit,
        search: search.trim() || undefined,
        region: regionFilter || undefined,
        category: categoryFilter.trim() || undefined,
        sort,
      })
      setProducts(response.products)
      setTotal(response.total)
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить товары.'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [page, limit, search, regionFilter, categoryFilter, sort])

  async function startEdit(product: AdminProduct) {
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      const fullProduct = await fetchAdminProduct(product.id, product.region)
      setSelectedProduct(fullProduct)
      setForm(fromProduct(fullProduct))
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить карточку товара.'),
      })
    }
  }

  function startCreate() {
    setSelectedProduct(null)
    setForm(EMPTY_FORM)
    setNotice(EMPTY_ADMIN_NOTICE)
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSaving(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      if (selectedProduct) {
        const updatedProduct = await updateAdminProduct(selectedProduct.id, selectedProduct.region, toPayload(form))
        setSelectedProduct(updatedProduct)
        setForm(fromProduct(updatedProduct))
        setNotice({ type: 'success', message: 'Товар обновлён.' })
      } else {
        const createdProduct = await createAdminProduct(toPayload(form))
        setSelectedProduct(createdProduct)
        setForm(fromProduct(createdProduct))
        setNotice({ type: 'success', message: 'Товар создан.' })
      }
      await onDataChanged()
      await loadProducts()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось сохранить товар.'),
      })
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!selectedProduct) {
      return
    }

    if (!window.confirm(`Удалить товар ${selectedProduct.display_name} (${selectedProduct.region})?`)) {
      return
    }

    setIsDeleting(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      await deleteAdminProduct(selectedProduct.id, selectedProduct.region)
      setSelectedProduct(null)
      setForm(EMPTY_FORM)
      setNotice({ type: 'success', message: 'Товар удалён.' })
      await onDataChanged()
      await loadProducts()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось удалить товар.'),
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const totalPages = Math.max(Math.ceil(total / limit), 1)

  return (
    <AdminSectionCard
      id="admin-products"
      title="Каталог и CRUD товаров"
      description="Редактирование карточек каталога по регионам, ценам, скидкам, PS Plus и метаданным."
      action={
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary" onClick={() => loadProducts()}>
            <RefreshCw size={16} />
            Обновить
          </button>
          <button type="button" className="btn-primary" onClick={startCreate}>
            <Plus size={16} />
            Новый товар
          </button>
        </div>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(380px,0.9fr)]">
        <div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_140px_180px_180px]">
            <input
              value={search}
              onChange={(event) => {
                setPage(1)
                setSearch(event.target.value)
              }}
              className="auth-input"
              placeholder="Поиск по ID, main_name или полному имени"
            />

            <select
              value={regionFilter}
              onChange={(event) => {
                setPage(1)
                setRegionFilter(event.target.value)
              }}
              className="auth-input"
            >
              <option value="">Все регионы</option>
              <option value="TR">TR</option>
              <option value="UA">UA</option>
              <option value="IN">IN</option>
            </select>

            <input
              value={categoryFilter}
              onChange={(event) => {
                setPage(1)
                setCategoryFilter(event.target.value)
              }}
              className="auth-input"
              placeholder="Фильтр по категории"
            />

            <select
              value={sort}
              onChange={(event) => {
                setPage(1)
                setSort(event.target.value as AdminProductSortMode)
              }}
              className="auth-input"
            >
              <option value="popular">Популярность</option>
              <option value="alphabet">По алфавиту</option>
            </select>
          </div>

          <AdminNotice state={notice} />

          <AdminTableShell>
            <div className="hidden grid-cols-[minmax(0,1.2fr)_90px_110px_90px_130px_130px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
              <span>Товар</span>
              <span>Регион</span>
              <span>Категория</span>
              <span>В избр.</span>
              <span>Цена</span>
              <span>Действия</span>
            </div>

            {isLoading ? (
              <div className="space-y-3 px-5 py-5">
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="h-20 animate-pulse rounded-[20px] bg-white/[0.04]" />
                ))}
              </div>
            ) : products.length ? (
              <div className="divide-y divide-white/6">
                {products.map((product) => (
                  <div key={`${product.id}-${product.region}`} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1.2fr)_90px_110px_90px_130px_130px] lg:items-center">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">{product.display_name}</p>
                      <p className="mt-1 truncate text-sm text-slate-400">{product.id}</p>
                    </div>
                    <div className="text-sm text-slate-300">{product.region}</div>
                    <div className="text-sm text-slate-300">{product.category || '—'}</div>
                    <div className="text-sm text-slate-300">{product.favorites_count}</div>
                    <div className="text-sm text-slate-300">
                      {product.price_try ?? product.price_uah ?? product.price_inr ?? product.price ?? '—'}
                    </div>
                    <div className="flex gap-2">
                      <button type="button" className="btn-secondary px-4 py-2 text-xs" onClick={() => startEdit(product)}>
                        <Pencil size={14} />
                        Изменить
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-5 py-8">
                <AdminEmptyState title="Товары не найдены" description="Попробуйте другие фильтры или создайте карточку вручную." />
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

        <div className="panel-soft rounded-[30px] p-5">
          <div className="flex items-center justify-between gap-4 border-b border-white/8 pb-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Редактор товара</p>
              <h3 className="mt-2 text-xl text-white">
                {selectedProduct ? 'Редактирование строки каталога' : 'Создание строки каталога'}
              </h3>
            </div>
          </div>

          <form className="mt-5 space-y-6" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <TextField label="ID товара" value={form.id} onChange={(value) => setForm((current) => ({ ...current, id: value }))} disabled={Boolean(selectedProduct)} />
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">Регион</label>
                <select
                  value={form.region}
                  onChange={(event) => setForm((current) => ({ ...current, region: event.target.value as ProductFormState['region'] }))}
                  className="auth-input"
                  disabled={Boolean(selectedProduct)}
                >
                  <option value="TR">TR</option>
                  <option value="UA">UA</option>
                  <option value="IN">IN</option>
                </select>
              </div>
              <TextField label="Полное имя" value={form.name} onChange={(value) => setForm((current) => ({ ...current, name: value }))} />
              <TextField label="Main name" value={form.main_name} onChange={(value) => setForm((current) => ({ ...current, main_name: value }))} />
              <TextField label="Категория" value={form.category} onChange={(value) => setForm((current) => ({ ...current, category: value }))} />
              <TextField label="Тип" value={form.type} onChange={(value) => setForm((current) => ({ ...current, type: value }))} />
              <TextField label="Edition" value={form.edition} onChange={(value) => setForm((current) => ({ ...current, edition: value }))} />
              <TextField label="Image URL" value={form.image} onChange={(value) => setForm((current) => ({ ...current, image: value }))} />
              <TextField label="Platforms" value={form.platforms} onChange={(value) => setForm((current) => ({ ...current, platforms: value }))} />
              <TextField label="Publisher" value={form.publisher} onChange={(value) => setForm((current) => ({ ...current, publisher: value }))} />
              <TextField label="Localization" value={form.localization} onChange={(value) => setForm((current) => ({ ...current, localization: value }))} />
              <TextField label="Rating" value={form.rating} onChange={(value) => setForm((current) => ({ ...current, rating: value }))} type="number" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <TextField label="Цена base" value={form.price} onChange={(value) => setForm((current) => ({ ...current, price: value }))} type="number" />
              <TextField label="Старая цена base" value={form.old_price} onChange={(value) => setForm((current) => ({ ...current, old_price: value }))} type="number" />
              <TextField label="PS цена base" value={form.ps_price} onChange={(value) => setForm((current) => ({ ...current, ps_price: value }))} type="number" />
              <TextField label="EA цена base" value={form.ea_price} onChange={(value) => setForm((current) => ({ ...current, ea_price: value }))} type="number" />
              <TextField label="TRY цена" value={form.price_try} onChange={(value) => setForm((current) => ({ ...current, price_try: value }))} type="number" />
              <TextField label="TRY старая" value={form.old_price_try} onChange={(value) => setForm((current) => ({ ...current, old_price_try: value }))} type="number" />
              <TextField label="UAH цена" value={form.price_uah} onChange={(value) => setForm((current) => ({ ...current, price_uah: value }))} type="number" />
              <TextField label="UAH старая" value={form.old_price_uah} onChange={(value) => setForm((current) => ({ ...current, old_price_uah: value }))} type="number" />
              <TextField label="INR цена" value={form.price_inr} onChange={(value) => setForm((current) => ({ ...current, price_inr: value }))} type="number" />
              <TextField label="INR старая" value={form.old_price_inr} onChange={(value) => setForm((current) => ({ ...current, old_price_inr: value }))} type="number" />
              <TextField label="PS Plus TRY" value={form.ps_plus_price_try} onChange={(value) => setForm((current) => ({ ...current, ps_plus_price_try: value }))} type="number" />
              <TextField label="PS Plus UAH" value={form.ps_plus_price_uah} onChange={(value) => setForm((current) => ({ ...current, ps_plus_price_uah: value }))} type="number" />
              <TextField label="PS Plus INR" value={form.ps_plus_price_inr} onChange={(value) => setForm((current) => ({ ...current, ps_plus_price_inr: value }))} type="number" />
              <TextField label="Скидка %" value={form.discount} onChange={(value) => setForm((current) => ({ ...current, discount: value }))} type="number" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <TextField label="Дата конца скидки" value={form.discount_end} onChange={(value) => setForm((current) => ({ ...current, discount_end: value }))} />
              <TextField label="Plus types" value={form.plus_types} onChange={(value) => setForm((current) => ({ ...current, plus_types: value }))} />
              <TextField label="PS Plus collection" value={form.ps_plus_collection} onChange={(value) => setForm((current) => ({ ...current, ps_plus_collection: value }))} />
              <TextField label="EA access" value={form.ea_access} onChange={(value) => setForm((current) => ({ ...current, ea_access: value }))} />
              <TextField label="Players min" value={form.players_min} onChange={(value) => setForm((current) => ({ ...current, players_min: value }))} type="number" />
              <TextField label="Players max" value={form.players_max} onChange={(value) => setForm((current) => ({ ...current, players_max: value }))} type="number" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={form.ps_plus}
                  onChange={(event) => setForm((current) => ({ ...current, ps_plus: event.target.checked }))}
                />
                Доступен в PS Plus
              </label>

              <label className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={form.players_online}
                  onChange={(event) => setForm((current) => ({ ...current, players_online: event.target.checked }))}
                />
                Есть онлайн
              </label>
            </div>

            <TextAreaField label="Search names" value={form.search_names} onChange={(value) => setForm((current) => ({ ...current, search_names: value }))} />
            <TextAreaField label="Tags" value={form.tags} onChange={(value) => setForm((current) => ({ ...current, tags: value }))} />
            <TextAreaField label="Description" value={form.description} onChange={(value) => setForm((current) => ({ ...current, description: value }))} />
            <TextAreaField label="Compound" value={form.compound} onChange={(value) => setForm((current) => ({ ...current, compound: value }))} />
            <TextAreaField label="Info" value={form.info} onChange={(value) => setForm((current) => ({ ...current, info: value }))} />

            <div className="flex flex-wrap gap-3">
              <button type="submit" className="btn-primary" disabled={isSaving}>
                {isSaving ? 'Сохраняем...' : selectedProduct ? 'Сохранить изменения' : 'Создать товар'}
              </button>

              <button type="button" className="btn-secondary" onClick={startCreate}>
                Очистить
              </button>

              {selectedProduct ? (
                <button type="button" className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10" onClick={handleDelete} disabled={isDeleting}>
                  <Trash2 size={16} />
                  {isDeleting ? 'Удаляем...' : 'Удалить'}
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </div>
    </AdminSectionCard>
  )
}
