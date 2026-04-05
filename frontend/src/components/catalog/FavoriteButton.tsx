import clsx from 'clsx'
import { Heart } from 'lucide-react'
import type { MouseEvent } from 'react'

type FavoriteButtonProps = {
  active: boolean
  onClick: (event: MouseEvent<HTMLButtonElement>) => void
  variant?: 'card' | 'hero'
  className?: string
}

export function FavoriteButton({
  active,
  onClick,
  variant = 'card',
  className,
}: FavoriteButtonProps) {
  return (
    <button
      type="button"
      aria-label={active ? 'Удалить из избранного' : 'Добавить в избранное'}
      aria-pressed={active}
      onClick={onClick}
      className={clsx(
        'inline-flex items-center justify-center border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-200/70',
        variant === 'card'
          ? 'h-10 w-10 rounded-full border-white/12 bg-slate-950/75 text-white shadow-lg backdrop-blur-md hover:border-rose-300/60 hover:bg-slate-950'
          : 'h-12 w-12 rounded-2xl border-white/15 bg-slate-950/70 text-white shadow-lg backdrop-blur-md hover:border-rose-300/60 hover:bg-slate-950',
        active && 'border-rose-300/40 bg-rose-500 text-white shadow-[0_10px_30px_rgba(244,63,94,0.35)]',
        className,
      )}
    >
      <Heart className={clsx('h-4 w-4 transition', variant === 'hero' && 'h-5 w-5', active && 'fill-current')} />
    </button>
  )
}
