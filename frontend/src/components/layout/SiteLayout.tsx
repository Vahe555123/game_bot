import { Heart, Menu, Sparkles, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useFavorites } from '../../context/FavoritesContext'

const DESKTOP_NAV_BUTTON_CLASS = 'btn-secondary min-h-[48px] px-5'
const MOBILE_NAV_BUTTON_CLASS = 'btn-secondary min-h-[48px] text-center'

function UserBadge() {
  const { user } = useAuth()

  if (!user) {
    return null
  }

  const name =
    [user.first_name, user.last_name].filter(Boolean).join(' ').trim() ||
    user.username ||
    user.email ||
    'Профиль'

  return (
    <div className="hidden min-h-[48px] items-center whitespace-nowrap rounded-full border border-white/10 bg-white/5 px-5 text-sm font-medium text-slate-100 xl:inline-flex">
      {name}
    </div>
  )
}

function FavoritesBadge({ count }: { count: number }) {
  if (!count) {
    return null
  }

  return (
    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-white/12 px-1.5 text-[11px] font-semibold leading-none text-white">
      {count}
    </span>
  )
}

export function SiteLayout() {
  const [isOpen, setIsOpen] = useState(false)
  const { isAuthenticated, user } = useAuth()
  const { favorites } = useFavorites()
  const telegramUrl = import.meta.env.VITE_TELEGRAM_BOT_URL

  return (
    <div className="relative min-h-screen">
      <header className="sticky top-0 z-40 border-b border-white/8 bg-slate-950/60 backdrop-blur-xl">
        <div className="container flex h-20 items-center justify-between gap-4">
          <Link to="/" className="flex min-w-0 items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-300 via-brand-500 to-sky-700 shadow-glow">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-display text-lg text-white">PS Store Web</p>
              <p className="truncate text-xs uppercase tracking-[0.26em] text-brand-200/80">miniapp inspired</p>
            </div>
          </Link>

          <div className="hidden items-center gap-3 md:flex">
            <UserBadge />

            {telegramUrl ? (
              <a href={telegramUrl} target="_blank" rel="noreferrer" className={DESKTOP_NAV_BUTTON_CLASS}>
                Открыть бота
              </a>
            ) : null}

            <Link to="/favorites" className={`${DESKTOP_NAV_BUTTON_CLASS} min-w-[164px]`}>
              <Heart size={16} />
              <span>Избранное</span>
              <FavoritesBadge count={favorites.length} />
            </Link>

            {isAuthenticated ? (
              <>
                <Link to="/profile" className={`${DESKTOP_NAV_BUTTON_CLASS} min-w-[144px]`}>
                  <UserRound size={16} />
                  <span>Профиль</span>
                </Link>
                {user?.is_admin ? (
                  <Link to="/admin" className={DESKTOP_NAV_BUTTON_CLASS}>
                    Админка
                  </Link>
                ) : null}
              </>
            ) : (
              <Link to="/login" className={DESKTOP_NAV_BUTTON_CLASS}>
                Войти
              </Link>
            )}

            {!isAuthenticated ? (
              <Link to="/register" className={DESKTOP_NAV_BUTTON_CLASS}>
                Регистрация
              </Link>
            ) : null}

            <Link to="/catalog" className="btn-primary min-h-[48px] px-6">
              В каталог
            </Link>
          </div>

          <button
            type="button"
            className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-white md:hidden"
            onClick={() => setIsOpen((value) => !value)}
            aria-label="Открыть меню"
          >
            <Menu size={18} />
          </button>
        </div>

        {isOpen ? (
          <div className="border-t border-white/8 bg-slate-950/90 px-4 pb-4 pt-3 md:hidden">
            <div className="mx-auto flex max-w-6xl flex-col gap-2">
              {telegramUrl ? (
                <a
                  href={telegramUrl}
                  target="_blank"
                  rel="noreferrer"
                  className={MOBILE_NAV_BUTTON_CLASS}
                  onClick={() => setIsOpen(false)}
                >
                  Открыть бота
                </a>
              ) : null}

              <Link to="/favorites" onClick={() => setIsOpen(false)} className={MOBILE_NAV_BUTTON_CLASS}>
                <Heart size={16} />
                <span>Избранное</span>
                <FavoritesBadge count={favorites.length} />
              </Link>

              {isAuthenticated ? (
                <>
                  <Link to="/profile" onClick={() => setIsOpen(false)} className={MOBILE_NAV_BUTTON_CLASS}>
                    <UserRound size={16} />
                    <span>Профиль</span>
                  </Link>
                  {user?.is_admin ? (
                    <Link to="/admin" onClick={() => setIsOpen(false)} className={MOBILE_NAV_BUTTON_CLASS}>
                      Админка
                    </Link>
                  ) : null}
                </>
              ) : (
                <>
                  <Link to="/login" onClick={() => setIsOpen(false)} className={MOBILE_NAV_BUTTON_CLASS}>
                    Войти
                  </Link>
                  <Link to="/register" onClick={() => setIsOpen(false)} className={MOBILE_NAV_BUTTON_CLASS}>
                    Регистрация
                  </Link>
                </>
              )}

              <Link to="/catalog" onClick={() => setIsOpen(false)} className="btn-primary mt-2 min-h-[48px] text-center">
                В каталог
              </Link>
            </div>
          </div>
        ) : null}
      </header>

      <main className="relative z-10">
        <Outlet />
      </main>

    </div>
  )
}
