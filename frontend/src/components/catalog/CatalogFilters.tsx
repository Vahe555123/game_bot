import clsx from 'clsx'
import { Check, RotateCcw } from 'lucide-react'
import type { CatalogFilterState } from '../../types/catalog'
import {
  GAME_LANGUAGE_OPTIONS,
  PLAYER_OPTIONS,
  PLATFORM_OPTIONS,
  PRICE_CURRENCY_OPTIONS,
  PRODUCT_KIND_OPTIONS,
  hasActiveCatalogFilters,
} from '../../utils/catalogFilters'

type CatalogFiltersProps = {
  categories: string[]
  draftFilters: CatalogFilterState
  onDraftChange: (partial: Partial<CatalogFilterState>) => void
  onReset: () => void
  onApply: () => void
  className?: string
}

type SelectFieldProps = {
  value: string
  options: ReadonlyArray<{ value: string; label: string }>
  onChange: (value: string) => void
  className?: string
}

function SelectField({ value, options, onChange, className }: SelectFieldProps) {
  return (
    <label className={clsx('block', className)}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[46px] w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-xs text-white outline-none transition focus:border-brand-300/60 md:rounded-2xl md:text-sm"
      >
        {options.map((option) => (
          <option key={option.value || 'empty'} value={option.value} className="bg-slate-900 text-white">
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function CatalogFilters({
  categories,
  draftFilters,
  onDraftChange,
  onReset,
  onApply,
  className,
}: CatalogFiltersProps) {
  const hasActiveFilters = hasActiveCatalogFilters(draftFilters)
  const categoryOptions = [
    { value: '', label: 'Все жанры игр' },
    ...categories.map((category) => ({ value: category, label: category })),
  ]

  return (
    <div className={clsx('space-y-3', className)}>
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-5">
        <SelectField
          value={draftFilters.productKind}
          options={PRODUCT_KIND_OPTIONS}
          onChange={(productKind) => onDraftChange({ productKind })}
        />

        <SelectField
          value={draftFilters.category}
          options={categoryOptions}
          onChange={(category) => onDraftChange({ category })}
        />

        <SelectField
          value={draftFilters.platform}
          options={PLATFORM_OPTIONS}
          onChange={(platform) => onDraftChange({ platform })}
        />

        <SelectField value={draftFilters.players} options={PLAYER_OPTIONS} onChange={(players) => onDraftChange({ players })} />

        <SelectField
          value={draftFilters.gameLanguage}
          options={GAME_LANGUAGE_OPTIONS}
          onChange={(gameLanguage) => onDraftChange({ gameLanguage })}
        />
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-6 xl:grid-cols-8">
        <label className="block lg:col-span-2 xl:col-span-1">
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={draftFilters.minPrice}
            onChange={(event) => onDraftChange({ minPrice: event.target.value })}
            placeholder="Мин. цена"
            className="min-h-[46px] w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-xs text-white outline-none transition placeholder:text-slate-500 focus:border-brand-300/60 md:rounded-2xl md:text-sm"
          />
        </label>

        <label className="block lg:col-span-2 xl:col-span-1">
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={draftFilters.maxPrice}
            onChange={(event) => onDraftChange({ maxPrice: event.target.value })}
            placeholder="Макс. цена"
            className="min-h-[46px] w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-xs text-white outline-none transition placeholder:text-slate-500 focus:border-brand-300/60 md:rounded-2xl md:text-sm"
          />
        </label>

        <SelectField
          value={draftFilters.priceCurrency}
          options={PRICE_CURRENCY_OPTIONS}
          onChange={(priceCurrency) => onDraftChange({ priceCurrency })}
          className="min-w-[128px] lg:col-span-2 xl:col-span-1"
        />

        <label className="flex min-h-[46px] cursor-pointer items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-100 transition hover:border-brand-400/40 md:rounded-2xl lg:col-span-2 xl:col-span-1">
          <span className="whitespace-nowrap">Только со скидкой</span>
          <input
            type="checkbox"
            checked={draftFilters.hasDiscount}
            onChange={(event) => onDraftChange({ hasDiscount: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>

        <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-slate-100 md:rounded-2xl lg:col-span-2 xl:col-span-2">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Доступны в подписке</p>

          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex min-h-[46px] cursor-pointer items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/30 px-3 py-2.5 text-sm transition hover:border-brand-400/40">
              <span className="whitespace-nowrap">PS Plus Extra</span>
              <input
                type="checkbox"
                checked={draftFilters.hasPsPlus}
                onChange={(event) => onDraftChange({ hasPsPlus: event.target.checked })}
                className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
              />
            </label>

            <label className="flex min-h-[46px] cursor-pointer items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/30 px-3 py-2.5 text-sm transition hover:border-brand-400/40">
              <span className="whitespace-nowrap">EA Play</span>
              <input
                type="checkbox"
                checked={draftFilters.hasEaAccess}
                onChange={(event) => onDraftChange({ hasEaAccess: event.target.checked })}
                className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
              />
            </label>
          </div>
        </div>

        <div className="grid gap-2 sm:col-span-2 lg:col-span-6 xl:col-span-2 xl:grid-cols-2">
          <button
            type="button"
            onClick={onReset}
            className={clsx(
              'btn-secondary min-h-[46px] w-full justify-center px-4 text-sm',
              !hasActiveFilters && draftFilters.sort === 'popular' && 'opacity-70',
            )}
          >
            <RotateCcw size={16} />
            Сбросить
          </button>

          <button
            type="button"
            onClick={onApply}
            className="btn-primary min-h-[46px] w-full justify-center px-5 text-sm"
          >
            <Check size={16} />
            Применить
          </button>
        </div>
      </div>
    </div>
  )
}
