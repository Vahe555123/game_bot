import { Heart, Menu, MessageCircle, Shield, Sparkles, UserRound, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useFavorites } from '../../context/FavoritesContext'
import { AuthModal } from '../auth/AuthModal'
import { buildAuthModalPath, buildBaseAuthPath, normalizeAuthModalView } from '../auth/authModalState'

const DESKTOP_NAV_LINK_CLASS =
  'inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/[0.06] hover:text-white'
const DESKTOP_ACTION_BUTTON_CLASS = 'btn-secondary min-h-[44px] px-4'
const MOBILE_MENU_LINK_CLASS =
  'flex min-h-[48px] items-center justify-center gap-2 rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3 text-center text-sm font-medium text-slate-100 transition hover:border-brand-300/50 hover:bg-brand-500/10'

const PARTNER_LINKS = [
  { label: 'Турция', href: 'https://romanomak.ru/category/120642' },
  { label: 'Индия', href: 'https://romanomak.ru/category/143863' },
  { label: 'Украина', href: 'https://romanomak.ru/category/101787' },
  { label: 'Польша', href: 'https://romanomak.ru/category/120397' },
  { label: 'Подписки', href: 'https://romanomak.ru/category/139773' },
] as const

type ActionLinkProps = {
  href?: string
  to?: string
  external?: boolean
  className: string
  onClick?: () => void
  children: ReactNode
}

type IconLinkProps = {
  href?: string
  to?: string
  external?: boolean
  className: string
  icon?: LucideIcon
  iconNode?: ReactNode
  label: string
  onClick?: () => void
}

function PsPlusMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" aria-hidden="true">
      <rect x="9" y="2.5" width="6" height="19" rx="3" fill="#facc15" />
      <rect x="2.5" y="9" width="19" height="6" rx="3" fill="#facc15" />
      <circle cx="6.3" cy="6.2" r="1.15" fill="#0f172a" />
      <path d="M17.2 4.9l1.7 1.7-1.7 1.7-1.7-1.7z" fill="#0f172a" />
      <path d="M5.3 17h2v2h-2z" fill="#0f172a" />
      <path d="M16.9 16.8h2.1v2.1h-2.1z" fill="#0f172a" />
    </svg>
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

function ActionLink({ href, to, external, className, onClick, children }: ActionLinkProps) {
  if (to) {
    return (
      <Link to={to} className={className} onClick={onClick}>
        {children}
      </Link>
    )
  }

  if (!href) {
    return null
  }

  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noreferrer' : undefined}
      className={className}
      onClick={onClick}
    >
      {children}
    </a>
  )
}

function IconLink({ href, to, external, className, icon: Icon, iconNode, label, onClick }: IconLinkProps) {
  return (
    <ActionLink href={href} to={to} external={external} className={className} onClick={onClick}>
      {iconNode ? (
        iconNode
      ) : (
        <>
          {Icon ? <Icon size={16} /> : null}
          <span>{label}</span>
        </>
      )}
    </ActionLink>
  )
}

export function SiteLayout() {
  const [isOpen, setIsOpen] = useState(false)
  const [isSupportOpen, setIsSupportOpen] = useState(false)
  const { isAuthenticated, user } = useAuth()
  const { favorites } = useFavorites()
  const location = useLocation()
  const navigate = useNavigate()
  const telegramUrl = import.meta.env.VITE_TELEGRAM_BOT_URL
  const managerTelegramUrl = import.meta.env.VITE_MANAGER_TELEGRAM_URL || telegramUrl
  const supportVkUrl = import.meta.env.VITE_SUPPORT_VK_URL
  const supportMaxUrl = import.meta.env.VITE_SUPPORT_MAX_URL
  const authView = normalizeAuthModalView(new URLSearchParams(location.search).get('auth'))
  const supportLinks = [
    managerTelegramUrl ? { label: 'Телеграм', href: managerTelegramUrl } : null,
    supportVkUrl ? { label: 'ВКонтакте', href: supportVkUrl } : null,
    supportMaxUrl ? { label: 'Max', href: supportMaxUrl } : null,
  ].filter((item): item is { label: string; href: string } => Boolean(item))

  function closeMobileMenu() {
    setIsOpen(false)
  }

  function openAuthModal() {
    navigate(buildAuthModalPath(location, 'login', buildBaseAuthPath(location)))
  }

  function openMobileAuthModal() {
    closeMobileMenu()
    openAuthModal()
  }

  return (
    <div className="relative min-h-screen">
      <header className="sticky top-0 z-40 border-b border-white/8 bg-slate-950/60 backdrop-blur-xl">
        <div className="container flex min-h-20 items-center gap-4 py-4">
          <Link to="/" className="flex min-w-0 shrink-0 items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-300 via-brand-500 to-sky-700 shadow-glow">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-display text-lg text-white">PS Store Web</p>
              <p className="truncate text-xs uppercase tracking-[0.26em] text-brand-200/80">miniapp inspired</p>
            </div>
          </Link>

          <div className="hidden min-w-0 flex-1 items-center justify-between gap-4 lg:flex">
            <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <ActionLink to="/catalog?hasDiscount=true" className={DESKTOP_NAV_LINK_CLASS}>
                Скидки
              </ActionLink>
              <ActionLink to="/catalog?hasPsPlus=true" className={DESKTOP_NAV_LINK_CLASS}>
                <PsPlusMark />
                <span>PS PLUS</span>
              </ActionLink>

              {PARTNER_LINKS.map((item) => (
                <ActionLink key={item.label} href={item.href} external className={DESKTOP_NAV_LINK_CLASS}>
                  {item.label}
                </ActionLink>
              ))}

              <ActionLink to="/help" className={DESKTOP_NAV_LINK_CLASS}>
                Помощь
              </ActionLink>
            </nav>

            <div className="flex shrink-0 items-center gap-2">
              {telegramUrl ? (
                <ActionLink href={telegramUrl} external className={DESKTOP_NAV_LINK_CLASS}>
                  Бот
                </ActionLink>
              ) : null}

              <IconLink
                to="/favorites"
                className={DESKTOP_ACTION_BUTTON_CLASS}
                icon={Heart}
                label="Избранное"
                iconNode={
                  <>
                    <Heart size={16} />
                    <span>Избранное</span>
                    <FavoritesBadge count={favorites.length} />
                  </>
                }
              />

              {isAuthenticated ? (
                <>
                  <ActionLink href="https://oplata.info" external className={DESKTOP_ACTION_BUTTON_CLASS}>
                    Мои покупки
                  </ActionLink>

                  <IconLink to="/profile" className={DESKTOP_ACTION_BUTTON_CLASS} icon={UserRound} label="Профиль" />

                  {user?.is_admin ? (
                    <IconLink to="/admin" className={DESKTOP_ACTION_BUTTON_CLASS} icon={Shield} label="Админка" />
                  ) : null}
                </>
              ) : (
                <button type="button" onClick={openAuthModal} className={DESKTOP_ACTION_BUTTON_CLASS}>
                  Вход
                </button>
              )}
            </div>
          </div>

          <button
            type="button"
            className="ml-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-white lg:hidden"
            onClick={() => setIsOpen((value) => !value)}
            aria-label="Открыть меню"
          >
            <Menu size={18} />
          </button>
        </div>

        {isOpen ? (
          <div className="border-t border-white/8 bg-slate-950/90 px-4 pb-4 pt-3 lg:hidden">
            <div className="mx-auto flex max-w-6xl flex-col gap-2">
              <ActionLink to="/catalog?hasDiscount=true" className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                Скидки
              </ActionLink>

              <ActionLink to="/catalog?hasPsPlus=true" className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                <PsPlusMark />
                <span>PS PLUS</span>
              </ActionLink>

              {PARTNER_LINKS.map((item) => (
                <ActionLink
                  key={item.label}
                  href={item.href}
                  external
                  className={MOBILE_MENU_LINK_CLASS}
                  onClick={closeMobileMenu}
                >
                  {item.label}
                </ActionLink>
              ))}

              <ActionLink to="/help" className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                Помощь
              </ActionLink>

              {telegramUrl ? (
                <ActionLink href={telegramUrl} external className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                  Открыть бота
                </ActionLink>
              ) : null}

              <IconLink
                to="/favorites"
                className={MOBILE_MENU_LINK_CLASS}
                icon={Heart}
                label="Избранное"
                onClick={closeMobileMenu}
                iconNode={
                  <>
                    <Heart size={16} />
                    <span>Избранное</span>
                    <FavoritesBadge count={favorites.length} />
                  </>
                }
              />

              {isAuthenticated ? (
                <>
                  <ActionLink
                    href="https://oplata.info"
                    external
                    className={MOBILE_MENU_LINK_CLASS}
                    onClick={closeMobileMenu}
                  >
                    Мои покупки
                  </ActionLink>

                  <IconLink
                    to="/profile"
                    className={MOBILE_MENU_LINK_CLASS}
                    icon={UserRound}
                    label="Профиль"
                    onClick={closeMobileMenu}
                  />

                  {user?.is_admin ? (
                    <IconLink
                      to="/admin"
                      className={MOBILE_MENU_LINK_CLASS}
                      icon={Shield}
                      label="Админка"
                      onClick={closeMobileMenu}
                    />
                  ) : null}
                </>
              ) : (
                <button type="button" onClick={openMobileAuthModal} className={MOBILE_MENU_LINK_CLASS}>
                  Вход / Регистрация
                </button>
              )}
            </div>
          </div>
        ) : null}
      </header>

      <main className="relative z-10">
        <Outlet />
      </main>

      {supportLinks.length ? (
        <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3">
          {isSupportOpen ? (
            <div className="w-[220px] rounded-[24px] border border-white/10 bg-slate-950/95 p-3 shadow-card backdrop-blur-xl">
              <p className="px-2 pb-2 text-xs uppercase tracking-[0.24em] text-slate-500">Задать вопрос</p>
              <div className="space-y-2">
                {supportLinks.map((item) => (
                  <ActionLink
                    key={item.label}
                    href={item.href}
                    external
                    className="flex min-h-[44px] items-center justify-center rounded-[18px] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-medium text-slate-100 transition hover:border-brand-300/50 hover:bg-brand-500/10"
                  >
                    {item.label}
                  </ActionLink>
                ))}
              </div>
            </div>
          ) : null}

          <button
            type="button"
            onClick={() => setIsSupportOpen((value) => !value)}
            className="flex min-h-[52px] items-center gap-2 rounded-full border border-brand-300/30 bg-brand-500 px-5 py-3 text-sm font-semibold text-white shadow-glow transition hover:bg-brand-400"
          >
            <MessageCircle size={18} />
            Задать вопрос
          </button>
        </div>
      ) : null}

      {authView ? <AuthModal view={authView} onClose={() => navigate(buildBaseAuthPath(location), { replace: true })} /> : null}
    </div>
  )
}
