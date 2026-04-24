import { ArrowRight, ChevronDown, ExternalLink, ShieldCheck, ShoppingBag } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { SectionHeader } from '../components/common/SectionHeader'
import { useHelpContent } from '../context/HelpContentContext'
import type { HelpContent } from '../types/help'

function HelpActionCard({
  title,
  description,
  buttonLabel,
  buttonUrl,
  socialLinks = [],
  icon,
}: {
  title: string
  description: string
  buttonLabel: string
  buttonUrl?: string | null
  socialLinks?: HelpContent['social_links']
  icon: ReactNode
}) {
  const actionLinks = [
    buttonUrl ? { label: buttonLabel, url: buttonUrl } : null,
    ...socialLinks.map((link) => ({ label: link.label, url: link.url })),
  ].filter((item): item is { label: string; url: string } => Boolean(item?.url))

  return (
    <article className="panel-soft rounded-[30px] p-6">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-100">{icon}</div>
      <h3 className="mt-5 text-2xl text-white">{title}</h3>
      <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-300">{description}</p>
      {actionLinks.length ? (
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          {actionLinks.map((link, index) => (
            <a key={`${link.label}-${link.url}`} href={link.url} target="_blank" rel="noreferrer" className={index === 0 ? 'btn-primary' : 'btn-secondary'}>
              {link.label}
              <ExternalLink size={16} />
            </a>
          ))}
        </div>
      ) : null}
    </article>
  )
}

export function HelpPage() {
  const { content, error, isLoading } = useHelpContent()
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0)

  useEffect(() => {
    setOpenFaqIndex(content.faq_items.length ? 0 : null)
  }, [content.faq_items])

  return (
    <div className="container space-y-10 py-10 md:space-y-12 md:py-14">
      <section className="panel mesh-bg overflow-hidden rounded-[34px] p-6 md:p-8">
        <SectionHeader eyebrow={content.eyebrow} title={content.title} description={content.subtitle} />

        {error ? <div className="auth-alert auth-alert-info mt-6">{error}</div> : null}

        <div className="mt-8 grid gap-5 lg:grid-cols-2">
          <HelpActionCard
            title={content.support_title}
            description={content.support_description}
            buttonLabel={content.support_button_label}
            buttonUrl={content.support_button_url}
            socialLinks={content.social_links || []}
            icon={<ShieldCheck size={20} />}
          />
          <HelpActionCard
            title={content.purchases_title}
            description={content.purchases_description}
            buttonLabel={content.purchases_button_label}
            buttonUrl={content.purchases_button_url}
            icon={<ShoppingBag size={20} />}
          />
        </div>
      </section>

      <section className="space-y-6">
        <SectionHeader
          eyebrow="Инструкции"
          title="Основные сценарии"
          description="Коротко собрали самое важное, чтобы вы быстро нашли нужное действие."
        />

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {content.sections.map((section) => (
            <article key={section.title} className="panel-soft rounded-[30px] p-6">
              <div className="pill border-brand-300/20 bg-brand-500/10 text-brand-50">Шаг</div>
              <h3 className="mt-5 text-2xl text-white">{section.title}</h3>
              <p className="mt-4 whitespace-pre-line text-sm leading-7 text-slate-300">{section.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-6">
        <SectionHeader
          eyebrow="FAQ"
          title="Частые вопросы"
          description="Ответы на самые частые ситуации по оплате, заказам и доступу к покупкам."
        />

        <div className="space-y-4">
          {content.faq_items.map((item, index) => {
            const isOpen = openFaqIndex === index

            return (
              <article key={`${item.question}-${index}`} className="panel-soft overflow-hidden rounded-[28px]">
                <button
                  type="button"
                  onClick={() => setOpenFaqIndex((current) => (current === index ? null : index))}
                  className="flex w-full items-center justify-between gap-4 px-5 py-5 text-left"
                >
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-brand-200/80">Вопрос {index + 1}</p>
                    <h3 className="mt-2 text-lg text-white">{item.question}</h3>
                  </div>
                  <span
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-slate-300 transition ${
                      isOpen ? 'rotate-180 text-white' : ''
                    }`}
                  >
                    <ChevronDown size={18} />
                  </span>
                </button>

                {isOpen ? (
                  <div className="border-t border-white/8 px-5 pb-5 pt-4">
                    <p className="whitespace-pre-line text-sm leading-7 text-slate-300">{item.answer}</p>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      </section>

      <section className="panel-soft rounded-[30px] p-6 md:p-7">
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-brand-200/80">Под рукой</p>
            <h2 className="mt-3 text-3xl text-white">Нужна история заказов прямо сейчас?</h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              Раздел с покупками открывается на `oplata.info` и привязан к вашему email для покупок.
            </p>
          </div>

          <a href="https://oplata.info" target="_blank" rel="noreferrer" className="btn-primary">
            Мои покупки
            <ArrowRight size={16} />
          </a>
        </div>

        {isLoading ? <p className="mt-5 text-sm text-slate-500">Обновляем данные страницы…</p> : null}
      </section>
    </div>
  )
}
