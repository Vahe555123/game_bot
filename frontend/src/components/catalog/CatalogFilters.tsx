import clsx from 'clsx'
import { BadgePercent, Gamepad2, Globe2, Layers3, SlidersHorizontal, Sparkles, Users2 } from 'lucide-react'
import type { ComponentType } from 'react'
import type { CatalogFilterState } from '../../types/catalog'
import {
  PLAYER_OPTIONS,
  PLATFORM_OPTIONS,
  REGION_OPTIONS,
  hasActiveCatalogFilters,
} from '../../utils/catalogFilters'

type CatalogFiltersProps = {
  categories: string[]
  draftFilters: CatalogFilterState
  onDraftChange: (partial: Partial<CatalogFilterState>) => void
  onApply: () => void
  onReset: () => void
  className?: string
}

type SelectFieldProps = {
  icon: ComponentType<{ size?: number; className?: string }>
  label: string
  value: string
  options: ReadonlyArray<{ value: string; label: string }>
  onChange: (value: string) => void
}

function SelectField({ icon: Icon, label, value, options, onChange }: SelectFieldProps) {
  return (
    <label className="space-y-2">
      <span className="flex items-center gap-2 text-sm font-semibold text-white">
        <Icon size={16} className="text-brand-300" />
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition focus:border-brand-300/60"
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
  onApply,
  onReset,
  className,
}: CatalogFiltersProps) {
  const hasActiveFilters = hasActiveCatalogFilters(draftFilters)
  const categoryOptions = [{ value: '', label: 'Все категории' }, ...categories.map((category) => ({ value: category, label: category }))]

  return (
    <aside className={clsx('panel-soft h-fit space-y-6 rounded-[28px] p-5', className)}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.34em] text-brand-200/80">Фильтры</p>
        </div>
        <span
          className={clsx(
            'pill',
            hasActiveFilters ? 'bg-brand-500/20 text-white' : 'bg-white/5 text-slate-300',
          )}
        >
          <SlidersHorizontal size={12} />
          {hasActiveFilters ? 'Есть активные' : 'Без фильтров'}
        </span>
      </div>

      <div className="grid gap-4">
        <SelectField
          icon={Layers3}
          label="Категория"
          value={draftFilters.category}
          options={categoryOptions}
          onChange={(category) => onDraftChange({ category })}
        />

        <SelectField
          icon={Globe2}
          label="Регион"
          value={draftFilters.region}
          options={REGION_OPTIONS}
          onChange={(region) => onDraftChange({ region })}
        />

        <SelectField
          icon={Gamepad2}
          label="Платформа"
          value={draftFilters.platform}
          options={PLATFORM_OPTIONS}
          onChange={(platform) => onDraftChange({ platform })}
        />

        <SelectField
          icon={Users2}
          label="Игроки"
          value={draftFilters.players}
          options={PLAYER_OPTIONS}
          onChange={(players) => onDraftChange({ players })}
        />
      </div>

      <section className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <BadgePercent size={16} className="text-brand-300" />
          Цена в рублях
        </div>
        <div className="grid grid-cols-2 gap-3">
          <input
            type="number"
            min="0"
            value={draftFilters.minPrice}
            onChange={(event) => onDraftChange({ minPrice: event.target.value })}
            placeholder="Мин. цена"
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-brand-300/60"
          />
          <input
            type="number"
            min="0"
            value={draftFilters.maxPrice}
            onChange={(event) => onDraftChange({ maxPrice: event.target.value })}
            placeholder="Макс. цена"
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-brand-300/60"
          />
        </div>
      </section>

      <section className="space-y-2">
        <label className="flex cursor-pointer items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:border-brand-400/40">
          <span className="flex items-center gap-2">
            <BadgePercent size={16} className="text-rose-300" />
            Только со скидкой
          </span>
          <input
            type="checkbox"
            checked={draftFilters.hasDiscount}
            onChange={(event) => onDraftChange({ hasDiscount: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>

        <label className="flex cursor-pointer items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:border-brand-400/40">
          <span className="flex items-center gap-2">
            <Gamepad2 size={16} className="text-amber-300" />
            Доступно в PS Plus
          </span>
          <input
            type="checkbox"
            checked={draftFilters.hasPsPlus}
            onChange={(event) => onDraftChange({ hasPsPlus: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>

        <label className="flex cursor-pointer items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:border-brand-400/40">
          <span className="flex items-center gap-2">
            <Sparkles size={16} className="text-cyan-300" />
            Доступно в EA Access
          </span>
          <input
            type="checkbox"
            checked={draftFilters.hasEaAccess}
            onChange={(event) => onDraftChange({ hasEaAccess: event.target.checked })}
            className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400 focus:ring-brand-400"
          />
        </label>
      </section>

      <div className="grid grid-cols-2 gap-3">
        <button type="button" onClick={onReset} className="btn-secondary w-full justify-center">
          Очистить
        </button>
        <button type="button" onClick={onApply} className="btn-primary w-full justify-center">
          Применить
        </button>
      </div>
    </aside>
  )
}
