import { CopyPlus, Heart, Pencil, Plus, RefreshCw, Trash2, UserRound, X } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import {
  createAdminProduct,
  deleteAdminProduct,
  deleteAdminProductFavorite,
  deleteAdminProductGroup,
  fetchAdminProduct,
  fetchAdminProducts,
  manualParseAdminProduct,
  updateAdminProduct,
} from '../../services/admin'
import type {
  AdminProduct,
  AdminProductDetails,
  AdminProductFavorite,
  AdminProductManualParseResponse,
  AdminProductPayload,
  AdminProductSortMode,
} from '../../types/admin'
import { getApiErrorMessage } from '../../utils/apiErrors'
import {
  AdminEmptyState,
  AdminNotice,
  AdminSectionCard,
  AdminTableShell,
  EMPTY_ADMIN_NOTICE,
  formatDateTime,
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

type ManualParseFormState = {
  ua_url: string
  tr_url: string
  in_url: string
  save_to_db: boolean
}

const EMPTY_MANUAL_PARSE_FORM: ManualParseFormState = {
  ua_url: '',
  tr_url: '',
  in_url: '',
  save_to_db: true,
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
    info: form.info.trim() || null,
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

function SummaryCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-slate-950/50 p-4">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
      {hint ? <p className="mt-2 text-xs leading-6 text-slate-400">{hint}</p> : null}
    </div>
  )
}

function ProductStatusBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-medium ${
        active
          ? 'border border-cyan-400/30 bg-cyan-500/12 text-cyan-100'
          : 'border border-white/10 bg-white/[0.03] text-slate-400'
      }`}
    >
      {label}
    </span>
  )
}

function formatCompactPrice(product: AdminProduct) {
  return product.price_try ?? product.price_uah ?? product.price_inr ?? product.price ?? '—'
}

function productKey(product: Pick<AdminProduct, 'id' | 'region'>) {
  return `${product.id}-${product.region}`
}

export function AdminProductsSection({ onDataChanged }: { onDataChanged: () => Promise<void> }) {
  const [products, setProducts] = useState<AdminProduct[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit] = useState(12)
  const [search, setSearch] = useState('')
  const [regionFilter, setRegionFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [missingRegionFilter, setMissingRegionFilter] = useState('')
  const [sort, setSort] = useState<AdminProductSortMode>('popular')
  const [isLoading, setIsLoading] = useState(true)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)
  const [activeProduct, setActiveProduct] = useState<AdminProductDetails | null>(null)
  const [editingProduct, setEditingProduct] = useState<AdminProductDetails | null>(null)
  const [productModalMode, setProductModalMode] = useState<'create' | 'view' | null>(null)
  const [isManualParseOpen, setIsManualParseOpen] = useState(false)
  const [manualParseForm, setManualParseForm] = useState<ManualParseFormState>(EMPTY_MANUAL_PARSE_FORM)
  const [manualParseResult, setManualParseResult] = useState<AdminProductManualParseResponse | null>(null)
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM)
  const [isSaving, setIsSaving] = useState(false)
  const [isManualParsing, setIsManualParsing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isDeletingGroup, setIsDeletingGroup] = useState(false)
  const [removingFavoriteId, setRemovingFavoriteId] = useState<number | null>(null)

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
        missing_region: missingRegionFilter || undefined,
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
  }, [page, limit, search, regionFilter, categoryFilter, sort, missingRegionFilter])

  function applyProductToList(product: AdminProductDetails) {
    setProducts((current) => {
      const next = [...current]
      const index = next.findIndex((item) => productKey(item) === productKey(product))
      if (index >= 0) {
        next[index] = product
        return next
      }
      return [product, ...next]
    })
  }

  async function loadProductDetails(productId: string, region: string) {
    const detail = await fetchAdminProduct(productId, region)
    setActiveProduct(detail)
    setEditingProduct(detail)
    setForm(fromProduct(detail))
    applyProductToList(detail)
    return detail
  }

  async function openProduct(product: AdminProduct) {
    setNotice(EMPTY_ADMIN_NOTICE)
    try {
      await loadProductDetails(product.id, product.region)
      setProductModalMode('view')
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить карточку товара.'),
      })
    }
  }

  function startCreate() {
    setActiveProduct(null)
    setEditingProduct(null)
    setProductModalMode('create')
    setForm(EMPTY_FORM)
    setNotice(EMPTY_ADMIN_NOTICE)
  }

  function openManualParse() {
    setIsManualParseOpen(true)
    setManualParseResult(null)
    setNotice(EMPTY_ADMIN_NOTICE)
  }

  function startCloneForRegion(region: 'TR' | 'UA' | 'IN') {
    if (!activeProduct) {
      return
    }
    setEditingProduct(null)
    setForm({
      ...fromProduct(activeProduct),
      region,
    })
    setProductModalMode('create')
    setNotice({
      type: 'info',
      message: `Создаётся новая строка для региона ${region} на основе текущего товара.`,
    })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSaving(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      if (editingProduct) {
        const updatedProduct = await updateAdminProduct(editingProduct.id, editingProduct.region, toPayload(form))
        setActiveProduct(updatedProduct)
        setEditingProduct(updatedProduct)
        setForm(fromProduct(updatedProduct))
        applyProductToList(updatedProduct)
        setProductModalMode('view')
        setNotice({ type: 'success', message: 'Товар обновлён.' })
      } else {
        const createdProduct = await createAdminProduct(toPayload(form))
        setActiveProduct(createdProduct)
        setEditingProduct(createdProduct)
        setForm(fromProduct(createdProduct))
        applyProductToList(createdProduct)
        setProductModalMode('view')
        setNotice({ type: 'success', message: 'Новая строка товара создана.' })
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

  async function handleManualParseSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsManualParsing(true)
    setManualParseResult(null)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      const response = await manualParseAdminProduct({
        ua_url: manualParseForm.ua_url.trim() || null,
        tr_url: manualParseForm.tr_url.trim() || null,
        in_url: manualParseForm.in_url.trim() || null,
        save_to_db: manualParseForm.save_to_db,
      })
      setManualParseResult(response)
      setNotice({
        type: 'success',
        message: `Ручной парсинг готов: ${response.final_total} записей, добавлено ${response.added_count}, обновлено ${response.updated_count}.`,
      })
      await onDataChanged()
      await loadProducts()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось выполнить ручной парсинг.'),
      })
    } finally {
      setIsManualParsing(false)
    }
  }

  async function handleDeleteCurrent() {
    if (!activeProduct) {
      return
    }

    if (!window.confirm(`Удалить строку ${activeProduct.display_name} (${activeProduct.region})?`)) {
      return
    }

    setIsDeleting(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      await deleteAdminProduct(activeProduct.id, activeProduct.region)
      setProducts((current) => current.filter((item) => productKey(item) !== productKey(activeProduct)))
      setActiveProduct(null)
      setEditingProduct(null)
      setProductModalMode(null)
      setForm(EMPTY_FORM)
      setNotice({ type: 'success', message: 'Строка товара удалена.' })
      await onDataChanged()
      await loadProducts()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось удалить строку товара.'),
      })
    } finally {
      setIsDeleting(false)
    }
  }

  async function handleDeleteGroup() {
    if (!activeProduct) {
      return
    }

    if (!window.confirm(`Удалить товар ${activeProduct.id} сразу во всех регионах?`)) {
      return
    }

    setIsDeletingGroup(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      const response = await deleteAdminProductGroup(activeProduct.id)
      setProducts((current) => current.filter((item) => item.id !== activeProduct.id))
      setActiveProduct(null)
      setEditingProduct(null)
      setProductModalMode(null)
      setForm(EMPTY_FORM)
      setNotice({ type: 'success', message: response.message })
      await onDataChanged()
      await loadProducts()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось удалить товар целиком.'),
      })
    } finally {
      setIsDeletingGroup(false)
    }
  }

  async function handleRemoveFavorite(favorite: AdminProductFavorite) {
    if (!activeProduct) {
      return
    }

    const userLabel = favorite.full_name || favorite.username || favorite.telegram_id || favorite.user_id
    if (!window.confirm(`Убрать товар из избранного у пользователя ${userLabel}?`)) {
      return
    }

    setRemovingFavoriteId(favorite.id)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      await deleteAdminProductFavorite(activeProduct.id, favorite.id)
      const refreshed = await fetchAdminProduct(activeProduct.id, activeProduct.region)
      setActiveProduct(refreshed)
      if (editingProduct && productKey(editingProduct) === productKey(refreshed)) {
        setEditingProduct(refreshed)
        setForm(fromProduct(refreshed))
      }
      applyProductToList(refreshed)
      setNotice({ type: 'success', message: 'Товар удалён из избранного пользователя.' })
      await onDataChanged()
      await loadProducts()
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось удалить товар из избранного.'),
      })
    } finally {
      setRemovingFavoriteId(null)
    }
  }

  const totalPages = Math.max(Math.ceil(total / limit), 1)

  return (
    <AdminSectionCard
      id="admin-products"
      title="Товары и полное управление каталогом"
      description="Просмотр всех полей товара, региональных строк, избранного и ручное управление карточками без похода в базу."
      action={
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary" onClick={() => loadProducts()}>
            <RefreshCw size={16} />
            Обновить
          </button>
          <button type="button" className="btn-secondary" onClick={openManualParse}>
            <CopyPlus size={16} />
            Ручной парсинг
          </button>
          <button type="button" className="btn-primary" onClick={startCreate}>
            <Plus size={16} />
            Новый товар
          </button>
        </div>
      }
    >
      <AdminNotice state={notice} />

      <div className="space-y-5">
        <div className="min-w-0 space-y-5">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(240px,1.2fr)_160px_200px_200px_240px]">
            <input
              value={search}
              onChange={(event) => {
                setPage(1)
                setSearch(event.target.value)
              }}
              className="auth-input"
              placeholder="Поиск по ID, названию, main_name"
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
              placeholder="Категория"
            />

            <select
              value={sort}
              onChange={(event) => {
                setPage(1)
                setSort(event.target.value as AdminProductSortMode)
              }}
              className="auth-input"
            >
              <option value="popular">По избранному</option>
              <option value="added_desc">Новые в базе</option>
              <option value="release_desc">Дата выхода: новые</option>
              <option value="alphabet">По алфавиту</option>
            </select>

            <select
              value={missingRegionFilter}
              onChange={(event) => {
                setPage(1)
                setMissingRegionFilter(event.target.value)
              }}
              className="auth-input"
              title="Показать товары, у которых отсутствует регион(ы)"
            >
              <option value="">Цены: все</option>
              <option value="any">Неполные (&lt; 3 регионов)</option>
              <option value="UA">Нет UA</option>
              <option value="TR">Нет TR</option>
              <option value="IN">Нет IN</option>
            </select>
          </div>

          <AdminTableShell>
            <div className="hidden grid-cols-[minmax(0,1.2fr)_70px_90px_120px_120px] gap-3 border-b border-white/8 px-5 py-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 lg:grid">
              <span>Товар</span>
              <span>Регион</span>
              <span>В избр.</span>
              <span>Цена</span>
              <span>Действия</span>
            </div>

            {isLoading ? (
              <div className="space-y-3 px-5 py-5">
                {Array.from({ length: 6 }).map((_, index) => (
                  <div key={index} className="h-24 animate-pulse rounded-[20px] bg-white/[0.04]" />
                ))}
              </div>
            ) : products.length ? (
              <div className="divide-y divide-white/6">
                {products.map((product) => {
                  const isActive = activeProduct ? productKey(product) === productKey(activeProduct) : false

                  return (
                    <div
                      key={productKey(product)}
                      className={`grid gap-4 px-5 py-4 transition lg:grid-cols-[minmax(0,1.2fr)_70px_90px_120px_120px] lg:items-center ${
                        isActive ? 'bg-cyan-500/[0.06]' : ''
                      }`}
                    >
                      <button type="button" className="min-w-0 text-left" onClick={() => openProduct(product)}>
                        <p className="truncate text-sm font-semibold text-white">{product.display_name}</p>
                        <p className="mt-1 truncate text-xs text-slate-400">{product.id}</p>
                        <p className="mt-2 truncate text-xs text-slate-500">
                          {product.category || 'Без категории'} • {product.localization || 'Без локализации'}
                        </p>
                      </button>

                      <div className="text-sm text-slate-300">{product.region}</div>
                      <div className="text-sm text-slate-300">{product.favorites_count}</div>
                      <div className="text-sm text-slate-300">{formatCompactPrice(product)}</div>
                      <div className="flex gap-2">
                        <button type="button" className="btn-secondary px-4 py-2 text-xs" onClick={() => openProduct(product)}>
                          <Pencil size={14} />
                          Открыть
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="px-5 py-8">
                <AdminEmptyState
                  title="Товары не найдены"
                  description="Попробуйте другие фильтры или создайте карточку вручную."
                />
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

        {isManualParseOpen ? (
          <div className="fixed inset-0 z-[75] flex items-end justify-center bg-slate-950/80 px-3 py-3 backdrop-blur-md md:items-center md:px-4 md:py-6">
            <div className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-[28px] border border-white/10 bg-slate-950 shadow-card">
              <div className="flex flex-col gap-3 border-b border-white/10 bg-slate-950/95 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-brand-200/80">Режим 4 из парсера</p>
                  <h3 className="mt-2 text-xl text-white">Ручной парсинг товара по регионам</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    UA ссылка может сама найти TR и IN. Если TR или IN указаны вручную, они парсятся отдельно.
                  </p>
                </div>
                <button type="button" className="btn-secondary px-4 py-2" onClick={() => setIsManualParseOpen(false)} disabled={isManualParsing}>
                  <X size={16} />
                  Закрыть
                </button>
              </div>

              <div className="overflow-y-auto p-4 sm:p-5 xl:p-6">
                <form className="space-y-5" onSubmit={handleManualParseSubmit}>
                  <TextField
                    label="UA URL"
                    value={manualParseForm.ua_url}
                    onChange={(value) => setManualParseForm((current) => ({ ...current, ua_url: value }))}
                    placeholder="https://store.playstation.com/ru-ua/product/..."
                    disabled={isManualParsing}
                  />
                  <TextField
                    label="TR URL"
                    value={manualParseForm.tr_url}
                    onChange={(value) => setManualParseForm((current) => ({ ...current, tr_url: value }))}
                    placeholder="Оставьте пустым, чтобы найти через UA"
                    disabled={isManualParsing}
                  />
                  <TextField
                    label="IN URL"
                    value={manualParseForm.in_url}
                    onChange={(value) => setManualParseForm((current) => ({ ...current, in_url: value }))}
                    placeholder="Оставьте пустым, чтобы найти через UA"
                    disabled={isManualParsing}
                  />

                  <label className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-200">
                    <input
                      type="checkbox"
                      checked={manualParseForm.save_to_db}
                      onChange={(event) => setManualParseForm((current) => ({ ...current, save_to_db: event.target.checked }))}
                      disabled={isManualParsing}
                    />
                    Сразу загрузить спарсенные записи в products.db
                  </label>

                  <div className="flex flex-wrap gap-3">
                    <button type="submit" className="btn-primary" disabled={isManualParsing}>
                      {isManualParsing ? 'Парсим...' : 'Запустить парсинг'}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setManualParseForm(EMPTY_MANUAL_PARSE_FORM)
                        setManualParseResult(null)
                      }}
                      disabled={isManualParsing}
                    >
                      Очистить
                    </button>
                  </div>
                </form>

                {manualParseResult ? (
                  <div className="mt-6 space-y-4 rounded-[26px] border border-white/10 bg-white/[0.03] p-4">
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <SummaryCard label="Спарсено" value={manualParseResult.parsed_total} />
                      <SummaryCard label="В result.pkl" value={manualParseResult.result_count} />
                      <SummaryCard label="Добавлено" value={manualParseResult.added_count} />
                      <SummaryCard label="Обновлено" value={manualParseResult.updated_count} />
                    </div>

                    {manualParseResult.errors.length ? (
                      <div className="rounded-[18px] border border-amber-400/20 bg-amber-500/10 p-3 text-sm text-amber-100">
                        {manualParseResult.errors.join(' ')}
                      </div>
                    ) : null}

                    <div className="space-y-2">
                      {manualParseResult.records.map((record, index) => (
                        <div key={`${record.id}-${record.region}-${index}`} className="rounded-[18px] border border-white/8 bg-slate-950/45 p-3">
                          <p className="text-sm font-semibold text-white">
                            {record.name || record.main_name || record.id || 'Товар'} {record.region ? `(${record.region})` : ''}
                          </p>
                          <p className="mt-1 break-all text-xs text-slate-400">{record.id}</p>
                          <p className="mt-2 text-xs text-slate-500">
                            {record.edition || 'Базовое издание'} • {record.localization || 'Язык не указан'} • {record.price_rub ?? '—'} RUB
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {productModalMode ? (
          <div className="fixed inset-0 z-[70] flex items-end justify-center bg-slate-950/80 px-3 py-3 backdrop-blur-md md:items-center md:px-4 md:py-6">
            <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[28px] border border-white/10 bg-slate-950 shadow-card">
              <div className="flex flex-col gap-3 border-b border-white/10 bg-slate-950/95 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-brand-200/80">
                    {productModalMode === 'create' ? 'Новый товар' : 'Карточка товара'}
                  </p>
                  <h3 className="mt-2 text-xl text-white">
                    {productModalMode === 'create'
                      ? 'Создание новой строки каталога'
                      : activeProduct?.display_name || 'Товар'}
                  </h3>
                </div>
                <button type="button" className="btn-secondary px-4 py-2" onClick={() => setProductModalMode(null)}>
                  <X size={16} />
                  Закрыть
                </button>
              </div>

              {notice.message && notice.type !== 'idle' ? (
                <div className="px-4 pt-4 md:px-6">
                  <AdminNotice state={notice} />
                </div>
              ) : null}

              <div className="overflow-y-auto p-4 sm:p-5 xl:p-6">
                <div className="space-y-6">
                  <div className={`${productModalMode === 'create' ? 'hidden' : ''} panel-soft min-w-0 rounded-[30px] p-4 sm:p-5 xl:p-6`}>
            {activeProduct ? (
              <div className="space-y-5">
                <div className="flex flex-col gap-4 border-b border-white/8 pb-5 md:flex-row md:items-start">
                  <div className="h-28 w-28 overflow-hidden rounded-[24px] border border-white/10 bg-slate-950/60">
                    {activeProduct.image ? (
                      <img src={activeProduct.image} alt={activeProduct.display_name} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-slate-500">Нет картинки</div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Центр товара</p>
                    <h3 className="mt-2 text-2xl text-white">{activeProduct.display_name}</h3>
                    <p className="mt-2 break-all text-sm text-slate-400">{activeProduct.id}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <ProductStatusBadge active={activeProduct.has_discount} label="Есть скидка" />
                      <ProductStatusBadge active={activeProduct.has_ps_plus} label="PS Plus" />
                      <ProductStatusBadge active={activeProduct.has_ea_access} label="EA Access" />
                      <ProductStatusBadge active={activeProduct.players_online} label="Онлайн" />
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <SummaryCard label="Избранное" value={activeProduct.favorite_users_total} hint="Сколько пользователей добавили товар." />
                  <SummaryCard label="Региональные строки" value={activeProduct.regional_rows_total} hint={activeProduct.available_regions.join(', ') || 'Нет'} />
                  <SummaryCard label="Отсутствуют регионы" value={activeProduct.missing_regions.length || '0'} hint={activeProduct.missing_regions.join(', ') || 'Все регионы присутствуют'} />
                  <SummaryCard label="Локализация" value={activeProduct.localization || '—'} hint={activeProduct.category || 'Без категории'} />
                </div>

                <div className="rounded-[26px] border border-white/10 bg-slate-950/45 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">Региональные строки товара</p>
                      <p className="mt-1 text-xs text-slate-500">Быстро переключайтесь между строками каталога с одним ID.</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {activeProduct.missing_regions.map((region) => (
                        <button
                          key={region}
                          type="button"
                          className="btn-secondary px-3 py-2 text-xs"
                          onClick={() => startCloneForRegion(region as 'TR' | 'UA' | 'IN')}
                        >
                          <CopyPlus size={14} />
                          Создать {region}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3">
                    {activeProduct.regional_products.map((regionalProduct) => (
                      <div key={productKey(regionalProduct)} className="rounded-[22px] border border-white/8 bg-white/[0.03] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-white">{regionalProduct.region}</p>
                            <p className="mt-1 text-xs text-slate-400">
                              {regionalProduct.localization || 'Без локализации'} • Цена: {formatCompactPrice(regionalProduct)}
                            </p>
                          </div>
                          <button
                            type="button"
                            className="btn-secondary px-4 py-2 text-xs"
                            onClick={() => openProduct(regionalProduct)}
                          >
                            <Pencil size={14} />
                            Открыть строку
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[26px] border border-white/10 bg-slate-950/45 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">Избранное по пользователям</p>
                      <p className="mt-1 text-xs text-slate-500">Видно, кто добавил товар и когда. Отсюда же можно убрать товар из избранного.</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(activeProduct.favorites_by_region).map(([region, count]) => (
                        <span key={region} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-300">
                          {region}: {count}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4 space-y-3">
                    {activeProduct.favorites.length ? (
                      activeProduct.favorites.map((favorite) => (
                        <div key={favorite.id} className="flex flex-col gap-3 rounded-[22px] border border-white/8 bg-white/[0.03] p-4 md:flex-row md:items-center md:justify-between">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 text-sm font-semibold text-white">
                              <UserRound size={15} />
                              <span className="truncate">{favorite.full_name || favorite.username || `User #${favorite.user_id}`}</span>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                              <span>Telegram: {favorite.telegram_id ?? '—'}</span>
                              <span>Регион пользователя: {favorite.preferred_region ?? '—'}</span>
                              <span>Регион избранного: {favorite.region ?? '—'}</span>
                              <span>Email покупок: {favorite.payment_email ?? '—'}</span>
                              <span>Добавил: {formatDateTime(favorite.favorited_at)}</span>
                            </div>
                          </div>

                          <button
                            type="button"
                            className="btn-secondary border-rose-400/20 px-4 py-2 text-xs text-rose-100 hover:bg-rose-500/10"
                            onClick={() => handleRemoveFavorite(favorite)}
                            disabled={removingFavoriteId === favorite.id}
                          >
                            <Heart size={14} />
                            {removingFavoriteId === favorite.id ? 'Удаляем...' : 'Убрать из избранного'}
                          </button>
                        </div>
                      ))
                    ) : (
                      <AdminEmptyState
                        title="Этот товар пока не в избранном"
                        description="Как только пользователи начнут добавлять его в избранное, список появится здесь."
                      />
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <AdminEmptyState
                title="Товар не выбран"
                description="Откройте строку слева, чтобы увидеть все данные товара, регионы и список пользователей из избранного."
              />
            )}
          </div>

          <div className="panel-soft min-w-0 rounded-[30px] p-4 sm:p-5 xl:p-6">
            <div className="flex flex-col gap-4 border-b border-white/8 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Редактор товара</p>
                <h3 className="mt-2 text-xl text-white">
                  {editingProduct ? `Редактирование ${editingProduct.region}` : 'Создание новой строки каталога'}
                </h3>
              </div>

              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-secondary px-4 py-2 text-xs" onClick={startCreate}>
                  <Plus size={14} />
                  Пустая форма
                </button>

                {productModalMode === 'view' && activeProduct ? (
                  <button
                    type="button"
                    className="btn-secondary border-rose-400/20 px-4 py-2 text-xs text-rose-100 hover:bg-rose-500/10"
                    onClick={handleDeleteGroup}
                    disabled={isDeletingGroup}
                  >
                    <Trash2 size={14} />
                    {isDeletingGroup ? 'Удаляем...' : 'Удалить весь товар'}
                  </button>
                ) : null}
              </div>
            </div>

            <form className="mt-5 space-y-6" onSubmit={handleSubmit}>
              <div className="grid gap-4 md:grid-cols-2">
                <TextField label="ID товара" value={form.id} onChange={(value) => setForm((current) => ({ ...current, id: value }))} disabled={Boolean(editingProduct)} />
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Регион</label>
                  <select
                    value={form.region}
                    onChange={(event) => setForm((current) => ({ ...current, region: event.target.value as ProductFormState['region'] }))}
                    className="auth-input"
                    disabled={Boolean(editingProduct)}
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

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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
                  {isSaving ? 'Сохраняем...' : editingProduct ? 'Сохранить изменения' : 'Создать строку'}
                </button>

                <button type="button" className="btn-secondary" onClick={startCreate}>
                  Очистить
                </button>

                {productModalMode === 'view' && activeProduct ? (
                  <button
                    type="button"
                    className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10"
                    onClick={handleDeleteCurrent}
                    disabled={isDeleting}
                  >
                    <Trash2 size={16} />
                    {isDeleting ? 'Удаляем...' : 'Удалить текущую строку'}
                  </button>
                ) : null}
              </div>
            </form>
                  </div>
                </div>
              </div>
            </div>
          </div>
          ) : null}
      </div>
    </AdminSectionCard>
  )
}
