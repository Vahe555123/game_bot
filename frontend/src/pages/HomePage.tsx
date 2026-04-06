import { ArrowRight, BadgePercent, Layers3, ShieldCheck, Sparkles, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ProductCard } from '../components/catalog/ProductCard'
import { ProductSkeleton } from '../components/catalog/ProductSkeleton'
import { SectionHeader } from '../components/common/SectionHeader'
import { mockProducts } from '../data/mockProducts'
import { fetchCatalog, fetchCategories } from '../services/catalog'
import type { CatalogProduct } from '../types/catalog'

const highlights = [
  {
    title: 'Живой каталог',
    description: 'Те же продукты и цены, что уже работают в miniapp и боте.',
    icon: Layers3,
  },
  {
    title: 'Быстрый checkout',
    description: 'Платежная логика останется той же, просто в веб-оболочке.',
    icon: ShieldCheck,
  },
  {
    title: 'Сильные подборки',
    description: 'Скидки, PS Plus и региональные акценты вынесены на первый экран.',
    icon: Zap,
  },
]

export function HomePage() {
  const [discounts, setDiscounts] = useState<CatalogProduct[]>([])
  const [psPlus, setPsPlus] = useState<CatalogProduct[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [catalogTotal, setCatalogTotal] = useState(0)
  const [discountTotal, setDiscountTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [source, setSource] = useState<'api' | 'mock'>('api')

  useEffect(() => {
    let ignore = false

    ;(async () => {
      try {
        const [discountResponse, psPlusResponse, categoryResponse, previewResponse] = await Promise.all([
          fetchCatalog({ limit: 4, has_discount: true }),
          fetchCatalog({ limit: 4, has_ps_plus: true }),
          fetchCategories(),
          fetchCatalog({ limit: 1 }),
        ])

        if (!ignore) {
          setDiscounts(discountResponse.products)
          setPsPlus(psPlusResponse.products)
          setCategories(categoryResponse)
          setCatalogTotal(previewResponse.total)
          setDiscountTotal(discountResponse.total)
          setSource('api')
        }
      } catch {
        if (!ignore) {
          setDiscounts(mockProducts.slice(0, 4))
          setPsPlus(mockProducts.filter((product) => product.hasPsPlus).slice(0, 4))
          setCategories(['Экшен', 'Новинки', 'RPG', 'PS Plus', 'Спорт'])
          setCatalogTotal(mockProducts.length)
          setDiscountTotal(mockProducts.filter((product) => product.hasDiscount).length)
          setSource('mock')
        }
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    })()

    return () => {
      ignore = true
    }
  }, [])

  const telegramUrl = import.meta.env.VITE_TELEGRAM_BOT_URL

  return (
    <div className="container space-y-14 py-10 md:space-y-20 md:py-14">
      <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <div className="space-y-8">
          <span className="pill bg-brand-500/10 text-brand-50">
            <Sparkles size={14} className="text-brand-200" />
            Веб-версия на основе miniapp
          </span>

          <div className="space-y-5">
            <h1 className="max-w-3xl text-5xl leading-none text-white sm:text-6xl lg:text-7xl">
              PlayStation-каталог с атмосферой Telegram miniapp, но уже в формате сайта
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-300">
              Сохраняем узнаваемые карточки, бейджи скидок, региональные цены и темп miniapp,
              но даем больше воздуха, крупные подборки и удобный каталог для desktop и mobile web.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link to="/catalog" className="btn-primary">
              Открыть каталог
              <ArrowRight size={16} />
            </Link>
            {telegramUrl ? (
              <a href={telegramUrl} target="_blank" rel="noreferrer" className="btn-secondary">
                Открыть бота
              </a>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="panel-soft p-5">
              <p className="text-xs uppercase tracking-[0.3em] text-brand-200/80">Каталог</p>
              <p className="mt-3 font-display text-3xl text-white">{catalogTotal || '8+'}</p>
              <p className="mt-2 text-sm text-slate-400">товаров уже можно подключить в веб-оболочку</p>
            </div>
            <div className="panel-soft p-5">
              <p className="text-xs uppercase tracking-[0.3em] text-brand-200/80">Скидки</p>
              <p className="mt-3 font-display text-3xl text-white">{discountTotal || '4+'}</p>
              <p className="mt-2 text-sm text-slate-400">горячих позиций в центре внимания</p>
            </div>
            <div className="panel-soft p-5">
              <p className="text-xs uppercase tracking-[0.3em] text-brand-200/80">Источник</p>
              <p className="mt-3 font-display text-3xl text-white">{source === 'api' ? 'API' : 'Demo'}</p>
              <p className="mt-2 text-sm text-slate-400">дизайн сразу работает с текущим backend</p>
            </div>
          </div>
        </div>

        <div className="panel relative overflow-hidden p-6">
          <div className="mesh-bg absolute inset-0 opacity-80" />
          <div className="relative z-10 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.34em] text-brand-100/80">Hero spotlight</p>
                <h2 className="mt-2 font-display text-2xl text-white">Главная страница</h2>
              </div>
              <span className="pill bg-white/10 text-white">miniapp DNA</span>
            </div>

            <img
              src="/static/images/psplussub.png"
              alt="PS Plus"
              className="w-full rounded-[24px] border border-white/10 object-cover shadow-card"
            />

            <div className="grid gap-3 sm:grid-cols-2">
              {categories.slice(0, 4).map((category) => (
                <div
                  key={category}
                  className="rounded-2xl border border-white/10 bg-slate-950/55 px-4 py-3 text-sm text-slate-200"
                >
                  {category}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {highlights.map(({ title, description, icon: Icon }) => (
          <article key={title} className="panel-soft p-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-200">
              <Icon size={20} />
            </div>
            <h3 className="mt-5 font-display text-2xl text-white">{title}</h3>
            <p className="mt-3 text-sm leading-7 text-slate-300">{description}</p>
          </article>
        ))}
      </section>

      <section className="space-y-6">
        <SectionHeader
          eyebrow="Подборка"
          title="Горячие скидки в центре внимания"
          description=""
          action={
            <Link to="/catalog?hasDiscount=true" className="btn-secondary">
              Все скидки
            </Link>
          }
        />

        <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:gap-4 xl:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, index) => <ProductSkeleton key={index} />)
            : discounts.map((product) => <ProductCard key={`${product.id}-${product.region || 'all'}`} product={product} />)}
        </div>
      </section>

      <section className="space-y-6">
        <SectionHeader
          eyebrow="PS Plus"
          title="Отдельная зона для подписочных игр и premium-подборок"
          description="В miniapp это уже важный сценарий, поэтому на сайте он сразу получает самостоятельный блок с ясной визуальной подачей."
          action={
            <Link to="/catalog?hasPsPlus=true" className="btn-secondary">
              Смотреть PS Plus
            </Link>
          }
        />

        <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:gap-4 xl:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, index) => <ProductSkeleton key={index} />)
            : psPlus.map((product) => <ProductCard key={`${product.id}-${product.region || 'all'}`} product={product} />)}
        </div>
      </section>

      <section className="panel overflow-hidden p-6 md:p-8">
        <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
          <div>
            <span className="pill bg-white/10 text-brand-50">
              <BadgePercent size={14} className="text-rose-200" />
              Следом можно подключать auth и checkout
            </span>
            <h2 className="mt-5 font-display text-3xl text-white md:text-4xl">
              Базовый визуальный язык сайта уже готов для следующего этапа
            </h2>
            <p className="mt-4 max-w-xl text-base leading-8 text-slate-300">
              Главная и каталог собраны на React, Tailwind и Axios, используют твой текущий API и
              уже повторяют ритм miniapp: быстрые карточки, региональные акценты и акцент на
              скидках.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
              <p className="text-sm uppercase tracking-[0.26em] text-brand-200/80">Главная</p>
              <p className="mt-4 text-xl font-semibold text-white">hero, подборки, PS Plus, CTA</p>
            </div>
            <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
              <p className="text-sm uppercase tracking-[0.26em] text-brand-200/80">Каталог</p>
              <p className="mt-4 text-xl font-semibold text-white">поиск, фильтры, пагинация, live API</p>
            </div>
            <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
              <p className="text-sm uppercase tracking-[0.26em] text-brand-200/80">Следом</p>
              <p className="mt-4 text-xl font-semibold text-white">авторизация, профиль, checkout</p>
            </div>
            <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
              <p className="text-sm uppercase tracking-[0.26em] text-brand-200/80">Backend</p>
              <p className="mt-4 text-xl font-semibold text-white">Python/FastAPI остается основой</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
