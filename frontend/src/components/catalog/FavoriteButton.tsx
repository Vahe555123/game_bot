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
          ? active
            ? 'h-9 w-9 rounded-full border-rose-300/50 bg-slate-950/95 text-rose-500 shadow-[0_10px_30px_rgba(244,63,94,0.28)] md:h-10 md:w-10'
            : 'h-9 w-9 rounded-full border-white/12 bg-slate-950/75 text-white shadow-lg backdrop-blur-md hover:border-rose-300/60 hover:bg-slate-950 md:h-10 md:w-10'
          : active
            ? 'h-12 w-12 rounded-2xl border-rose-300/50 bg-slate-950/95 text-rose-500 shadow-[0_10px_30px_rgba(244,63,94,0.28)]'
            : 'h-12 w-12 rounded-2xl border-white/15 bg-slate-950/70 text-white shadow-lg backdrop-blur-md hover:border-rose-300/60 hover:bg-slate-950',
        className,
      )}
    >
      <Heart className={clsx('h-3.5 w-3.5 transition md:h-4 md:w-4', variant === 'hero' && 'h-5 w-5', active && 'fill-current')} />
    </button>
  )
}
