import clsx from 'clsx'
import {
  ChevronDown,
  Globe2,
  Heart,
  Home,
  Menu,
  MessageCircle,
  Search,
  Shield,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useFavorites } from '../../context/FavoritesContext'
import { useHelpContent } from '../../context/HelpContentContext'
import { SORT_OPTIONS } from '../../utils/catalogFilters'
import { AuthModal } from '../auth/AuthModal'
import { buildAuthModalPath, buildBaseAuthPath, normalizeAuthModalView } from '../auth/authModalState'

const DESKTOP_NAV_LINK_CLASS =
  'inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full px-2.5 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/[0.06] hover:text-white xl:px-3'
const DESKTOP_ACTION_BUTTON_CLASS = 'btn-secondary min-h-[44px] px-3 xl:px-4'
const MOBILE_MENU_LINK_CLASS =
  'flex min-h-[48px] items-center justify-start gap-3 rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-3 text-left text-sm font-medium text-slate-100 transition hover:border-brand-300/50 hover:bg-brand-500/10'

const COUNTRY_PARTNER_LINKS = [
  { label: 'Турция', code: 'TR', href: 'https://romanomak.ru/category/120642' },
  { label: 'Индия', code: 'IN', href: 'https://romanomak.ru/category/143863' },
  { label: 'Украина', code: 'UA', href: 'https://romanomak.ru/category/101787' },
  { label: 'Польша', code: 'PL', href: 'https://romanomak.ru/category/120397' },
] as const

const SUBSCRIPTIONS_PARTNER_LINK = {
  label: 'EA Play',
  href: 'https://romanomak.ru/category/124950',
} as const

const PS_PLUS_PARTNER_LINK = {
  label: 'PS PLUS',
  href: 'https://romanomak.ru/category/120182',
} as const

const DESKTOP_DROPDOWN_ITEM_CLASS =
  'flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-medium text-slate-300 transition hover:bg-brand-500/12 hover:text-white'

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

function DesktopCountriesDropdown() {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    function onPointerDown(event: MouseEvent | PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className="relative shrink-0" ref={rootRef}>
      <button
        type="button"
        className={clsx(
          DESKTOP_NAV_LINK_CLASS,
          open && 'bg-white/[0.08] text-white ring-1 ring-brand-400/25',
        )}
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        <Globe2 size={16} className="shrink-0 text-brand-200/90" aria-hidden />
        <span>Коды пополнения баланса</span>
        <ChevronDown
          size={16}
          className={clsx('shrink-0 opacity-70 transition-transform duration-200', open && 'rotate-180')}
          aria-hidden
        />
      </button>

      {open ? (
        <div
          className="absolute left-0 top-[calc(100%+0.5rem)] z-[60] min-w-[min(100vw-2rem,240px)] rounded-2xl border border-white/10 bg-slate-950/95 p-1.5 shadow-card backdrop-blur-xl ring-1 ring-white/[0.04]"
          role="menu"
        >
          <p className="px-3 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Выберите регион</p>
          <div className="flex flex-col gap-0.5">
            {COUNTRY_PARTNER_LINKS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                role="menuitem"
                className={DESKTOP_DROPDOWN_ITEM_CLASS}
                onClick={() => setOpen(false)}
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-[10px] font-bold tracking-wide text-brand-200">
                  {item.code}
                </span>
                {item.label}
              </a>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function buildCatalogSearch(search: string, locationSearch: string, extraParams: Record<string, string | null> = {}) {
  const params = new URLSearchParams(locationSearch)
  params.delete('page')
  params.delete('auth')

  if (search.trim()) {
    params.set('search', search.trim())
  } else {
    params.delete('search')
  }

  Object.entries(extraParams).forEach(([key, value]) => {
    if (value === null || value === '') {
      params.delete(key)
      return
    }

    params.set(key, value)
  })

  const query = params.toString()
  return query ? `/catalog?${query}` : '/catalog'
}

export function SiteLayout() {
  const [isOpen, setIsOpen] = useState(false)
  const [mobileCountriesOpen, setMobileCountriesOpen] = useState(false)
  const [isSupportOpen, setIsSupportOpen] = useState(false)
  const [isGlobalSearchOpen, setIsGlobalSearchOpen] = useState(false)
  const { isAuthenticated, user } = useAuth()
  const { favorites } = useFavorites()
  const { questionSupportLinks } = useHelpContent()
  const location = useLocation()
  const navigate = useNavigate()
  const currentCatalogParams = new URLSearchParams(location.search)
  const [globalSearch, setGlobalSearch] = useState(currentCatalogParams.get('search') || '')
  const telegramUrl = import.meta.env.VITE_TELEGRAM_BOT_URL
  const authView = normalizeAuthModalView(new URLSearchParams(location.search).get('auth'))
  const currentSort = currentCatalogParams.get('sort') || 'popular'
  const isCatalogPage = location.pathname === '/' || location.pathname === '/catalog'
  const isCatalogFiltersOpen = isCatalogPage && currentCatalogParams.get('filters') === 'open'
  const showCatalogControls = !isCatalogPage && !location.pathname.startsWith('/admin')

  useEffect(() => {
    if (!isSupportOpen || typeof document === 'undefined') {
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsSupportOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isSupportOpen])

  useEffect(() => {
    setGlobalSearch(new URLSearchParams(location.search).get('search') || '')
  }, [location.search])

  function closeMobileMenu() {
    setIsOpen(false)
    setMobileCountriesOpen(false)
  }

  function openAuthModal() {
    navigate(buildAuthModalPath(location, 'login', buildBaseAuthPath(location)))
  }

  function openMobileAuthModal() {
    closeMobileMenu()
    openAuthModal()
  }

  function submitGlobalSearch() {
    if (!globalSearch.trim()) {
      setIsGlobalSearchOpen(false)
    }

    navigate(buildCatalogSearch(globalSearch, location.search))
  }

  function toggleGlobalFilters() {
    navigate(
      buildCatalogSearch(globalSearch, location.search, {
        filters: isCatalogFiltersOpen ? null : 'open',
      }),
    )
  }

  function updateGlobalSort(sort: string) {
    navigate(
      buildCatalogSearch(globalSearch, location.search, {
        sort: sort === 'popular' ? null : sort,
      }),
    )
  }

  return (
    <div className="relative min-h-screen">
      <header className="sticky top-0 z-40 border-b border-white/8 bg-slate-950/60 backdrop-blur-xl">
        <div className="container flex min-h-[72px] items-center gap-3 py-3 md:min-h-20 md:gap-4 md:py-4">
          <Link to="/" className="flex min-w-0 shrink-0 items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-300 via-brand-500 to-sky-700 shadow-glow md:h-12 md:w-12">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-display text-base text-white sm:text-lg">PS Store Web</p>
              <p className="hidden truncate text-[10px] uppercase tracking-[0.22em] text-brand-200/80 sm:block md:text-xs md:tracking-[0.26em]">
                miniapp inspired
              </p>
            </div>
          </Link>

          <div className="hidden min-w-0 flex-1 items-center justify-end gap-3 lg:flex xl:gap-4">
            <nav className="flex min-w-0 flex-1 items-center justify-end gap-0.5 overflow-visible xl:gap-1">
              <div className="flex min-w-0 items-center justify-end gap-0.5 xl:gap-1">
                <ActionLink to="/" className={DESKTOP_NAV_LINK_CLASS}>
                  <Home size={16} />
                  Главная
                </ActionLink>
                <ActionLink to="/catalog?hasDiscount=true" className={DESKTOP_NAV_LINK_CLASS}>
                  Скидки
                </ActionLink>
                <ActionLink href={PS_PLUS_PARTNER_LINK.href} external className={DESKTOP_NAV_LINK_CLASS}>
                  <PsPlusMark />
                  <span>{PS_PLUS_PARTNER_LINK.label}</span>
                </ActionLink>
                <DesktopCountriesDropdown />
                <ActionLink href={SUBSCRIPTIONS_PARTNER_LINK.href} external className={DESKTOP_NAV_LINK_CLASS}>
                  {SUBSCRIPTIONS_PARTNER_LINK.label}
                </ActionLink>

                <ActionLink to="/help" className={DESKTOP_NAV_LINK_CLASS}>
                  Помощь
                </ActionLink>
              </div>
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
                  {/* <ActionLink href="https://oplata.info" external className={DESKTOP_ACTION_BUTTON_CLASS}>
                    Мои покупки
                  </ActionLink> */}

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
            className="ml-auto flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-white lg:hidden"
            onClick={() => setIsOpen((value) => !value)}
            aria-label="Открыть меню"
          >
            <Menu size={18} />
          </button>
        </div>

        {showCatalogControls ? (
          <div className="border-t border-white/[0.06] bg-gradient-to-b from-slate-950/60 to-slate-950/20">
            <div className="container flex flex-wrap items-center justify-end gap-2 py-3 md:flex-nowrap md:justify-center lg:py-4">
              <button
                type="button"
                onClick={() => setIsGlobalSearchOpen((value) => !value)}
                className={clsx(
                  'inline-flex min-h-[44px] shrink-0 items-center justify-center rounded-2xl border px-3 text-white transition md:hidden',
                  isGlobalSearchOpen ? 'border-brand-300/50 bg-brand-500/20' : 'border-white/10 bg-white/5',
                )}
                aria-label="Открыть поиск"
                aria-pressed={isGlobalSearchOpen}
              >
                <Search size={18} />
              </button>

              <label
                className={clsx(
                  'min-h-[44px] min-w-0 items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 text-sm text-white shadow-[0_18px_45px_rgba(8,18,34,0.22)] transition focus-within:border-brand-300/50 focus-within:bg-white/[0.07] md:flex md:flex-1 md:rounded-full md:px-4',
                  isGlobalSearchOpen ? 'order-2 flex basis-full' : 'hidden',
                )}
              >
                <Search size={16} className="shrink-0 text-brand-200" />
                <input
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      submitGlobalSearch()
                    }
                  }}
                  onBlur={submitGlobalSearch}
                  placeholder="Поиск игр и подписок..."
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-500"
                />
              </label>

              <button
                type="button"
                onClick={toggleGlobalFilters}
                className={clsx(
                  'inline-flex min-h-[44px] shrink-0 items-center justify-center gap-2 rounded-2xl border px-3 text-sm font-semibold text-white shadow-[0_18px_45px_rgba(8,18,34,0.18)] transition md:rounded-full md:px-4',
                  isCatalogFiltersOpen ? 'border-brand-300/50 bg-brand-500/20' : 'border-white/10 bg-white/5 hover:border-brand-300/50',
                )}
              >
                <SlidersHorizontal size={16} />
                <span className="hidden sm:inline">Фильтр</span>
              </button>

              <select
                value={currentSort}
                onChange={(event) => updateGlobalSort(event.target.value)}
                className="hidden min-h-[44px] shrink-0 rounded-full border border-white/10 bg-white/5 px-3 text-sm text-white outline-none transition focus:border-brand-300/50 sm:block"
                aria-label="Сортировка каталога"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value} className="bg-slate-900 text-white">
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : null}

        {isOpen ? (
          <div className="border-t border-white/8 bg-slate-950/90 px-4 pb-4 pt-3 lg:hidden">
            <div className="mx-auto flex max-w-6xl flex-col gap-2">
              <ActionLink to="/catalog?hasDiscount=true" className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                Скидки
              </ActionLink>

              <ActionLink to="/" className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                <Home size={18} />
                Главная
              </ActionLink>

              <ActionLink href={PS_PLUS_PARTNER_LINK.href} external className={MOBILE_MENU_LINK_CLASS} onClick={closeMobileMenu}>
                <PsPlusMark />
                <span>{PS_PLUS_PARTNER_LINK.label}</span>
              </ActionLink>

              <div className="overflow-hidden rounded-[18px] border border-white/10 bg-white/[0.02]">
                <button
                  type="button"
                  className="flex min-h-[48px] w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium text-slate-100 transition hover:bg-white/[0.04]"
                  aria-expanded={mobileCountriesOpen}
                  onClick={() => setMobileCountriesOpen((value) => !value)}
                >
                  <Globe2 size={18} className="shrink-0 text-brand-200/90" aria-hidden />
                  <span className="min-w-0 flex-1">Коды пополнения баланса</span>
                  <ChevronDown
                    size={18}
                    className={clsx('shrink-0 text-slate-400 transition-transform', mobileCountriesOpen && 'rotate-180')}
                    aria-hidden
                  />
                </button>
                {mobileCountriesOpen ? (
                  <div className="space-y-1 border-t border-white/8 px-2 pb-2 pt-2">
                    {COUNTRY_PARTNER_LINKS.map((item) => (
                      <ActionLink
                        key={item.label}
                        href={item.href}
                        external
                        className="flex min-h-[44px] items-center gap-3 rounded-xl border border-transparent bg-white/[0.03] px-3 py-2.5 text-sm font-medium text-slate-200 transition hover:border-brand-300/40 hover:bg-brand-500/10 hover:text-white"
                        onClick={closeMobileMenu}
                      >
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-[10px] font-bold tracking-wide text-brand-200">
                          {item.code}
                        </span>
                        {item.label}
                      </ActionLink>
                    ))}
                  </div>
                ) : null}
              </div>

              <ActionLink
                href={SUBSCRIPTIONS_PARTNER_LINK.href}
                external
                className={MOBILE_MENU_LINK_CLASS}
                onClick={closeMobileMenu}
              >
                {SUBSCRIPTIONS_PARTNER_LINK.label}
              </ActionLink>

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
                  {/* <ActionLink
                    href="https://oplata.info"
                    external
                    className={MOBILE_MENU_LINK_CLASS}
                    onClick={closeMobileMenu}
                  >
                    Мои покупки
                  </ActionLink> */}

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

      {questionSupportLinks.length ? (
        <div className="fixed bottom-3 right-3 z-40 flex flex-col items-end gap-2.5 sm:bottom-5 sm:right-5 sm:gap-3">
          <button
            type="button"
            onClick={() => setIsSupportOpen((value) => !value)}
            className="flex min-h-[48px] items-center gap-2 rounded-full border border-brand-300/30 bg-brand-500 px-4 py-3 text-sm font-semibold text-white shadow-glow transition hover:bg-brand-400 sm:min-h-[52px] sm:px-5"
          >
            <MessageCircle size={18} />
            Задать вопрос
          </button>
        </div>
      ) : null}

      {isSupportOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 px-4 py-6 backdrop-blur-md sm:px-6"
          onClick={() => setIsSupportOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-[28px] border border-white/15 bg-gradient-to-br from-slate-900/95 via-slate-900/90 to-[#0d1c31]/95 p-5 shadow-[0_32px_80px_rgba(0,0,0,0.5)] ring-1 ring-brand-300/20 sm:p-6"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-brand-200/85">Помощь</p>
                <h3 className="mt-2 text-2xl text-white">Связаться с нами</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Выберите удобный способ связи, и мы поможем с покупкой или заказом.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsSupportOpen(false)}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/[0.04] text-slate-200 transition hover:border-brand-300/50 hover:bg-brand-500/15"
                aria-label="Закрыть окно помощи"
              >
                x
              </button>
            </div>

            <div className="mt-5 space-y-2.5">
              {questionSupportLinks.map((item) => (
                <ActionLink
                  key={item.label}
                  href={item.url}
                  external
                  className="flex min-h-[46px] items-center justify-center rounded-[16px] border border-white/10 bg-white/[0.05] px-4 py-3 text-sm font-medium text-slate-100 transition hover:border-brand-300/60 hover:bg-brand-500/12"
                >
                  {item.label}
                </ActionLink>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {authView ? <AuthModal view={authView} onClose={() => navigate(buildBaseAuthPath(location), { replace: true })} /> : null}
    </div>
  )
}
