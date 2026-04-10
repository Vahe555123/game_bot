import clsx from 'clsx'
import { RotateCcw, Sparkles } from 'lucide-react'
import type { CatalogFilterState } from '../../types/catalog'
import {
  PLAYER_OPTIONS,
  PLATFORM_OPTIONS,
  PRICE_CURRENCY_OPTIONS,
  SORT_OPTIONS,
  hasActiveCatalogFilters,
} from '../../utils/catalogFilters'

type CatalogFiltersProps = {
  categories: string[]
  draftFilters: CatalogFilterState
  onDraftChange: (partial: Partial<CatalogFilterState>) => void
  onReset: () => void
  className?: string
}

type SelectFieldProps = {
  value: string
  options: ReadonlyArray<{ value: string; label: string }>
  onChange: (value: string) => void
}

function SelectField({ value, options, onChange }: SelectFieldProps) {
  return (
    <label className="block">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-[52px] w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition focus:border-brand-300/60 md:rounded-2xl"
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
  className,
}: CatalogFiltersProps) {
  const hasActiveFilters = hasActiveCatalogFilters(draftFilters)
  const categoryOptions = [{ value: '', label: 'Все жанры игр' }, ...categories.map((category) => ({ value: category, label: category }))]

  return (
    <div className={clsx('space-y-4', className)}>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SelectField value={draftFilters.sort} options={SORT_OPTIONS} onChange={(sort) => onDraftChange({ sort })} />

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
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <label className="block">
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={draftFilters.minPrice}
            onChange={(event) => onDraftChange({ minPrice: event.target.value })}
            placeholder="Мин. цена"
            className="min-h-[52px] w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-brand-300/60 md:rounded-2xl"
          />
        </label>

        <label className="block">
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={draftFilters.maxPrice}
            onChange={(event) => onDraftChange({ maxPrice: event.target.value })}
            placeholder="Макс. цена"
            className="min-h-[52px] w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-brand-300/60 md:rounded-2xl"
          />
        </label>

        <SelectField
          value={draftFilters.priceCurrency}
          options={PRICE_CURRENCY_OPTIONS}
          onChange={(priceCurrency) => onDraftChange({ priceCurrency })}
        />

        <label className="flex min-h-[56px] cursor-pointer items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:border-brand-400/40 md:rounded-2xl">
          <span>Только со скидкой</span>
          <input
            type="checkbox"
            checked={draftFilters.hasDiscount}
            onChange={(event) => onDraftChange({ hasDiscount: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>

        <label className="flex min-h-[56px] cursor-pointer items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:border-brand-400/40 md:rounded-2xl">
          <span>Доступно в PS Plus</span>
          <input
            type="checkbox"
            checked={draftFilters.hasPsPlus}
            onChange={(event) => onDraftChange({ hasPsPlus: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>

        <label className="flex min-h-[56px] cursor-pointer items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:border-brand-400/40 md:rounded-2xl">
          <span className="flex items-center gap-2">
            <Sparkles size={16} className="text-sky-300" />
            Доступно в EA PLAY
          </span>
          <input
            type="checkbox"
            checked={draftFilters.hasEaAccess}
            onChange={(event) => onDraftChange({ hasEaAccess: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>

        <button
          type="button"
          onClick={onReset}
          className={clsx(
            'btn-secondary min-h-[56px] w-full justify-center sm:col-span-2 lg:col-span-3 xl:col-span-6',
            !hasActiveFilters && draftFilters.sort === 'popular' && 'opacity-70',
          )}
        >
          <RotateCcw size={16} />
          Сбросить
        </button>
      </div>
    </div>
  )
}
