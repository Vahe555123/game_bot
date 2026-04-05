import { ShieldCheck, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

type AuthShellProps = {
  eyebrow: string
  title: string
  description: string
  children: ReactNode
  asideTitle?: string
  asideText?: string
}

const defaultHighlights = [
  'Регистрация через email и код подтверждения',
  'Логика профиля строится на данных miniapp',
  'Сессия сохраняется через безопасную cookie',
]

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  asideTitle = 'Сайт в стиле miniapp',
  asideText = 'Те же регионы, PSN-поля и привычная логика магазина, но уже в полноценном web-интерфейсе.',
}: AuthShellProps) {
  return (
    <div className="container py-10 md:py-14">
      <div className="grid gap-8 lg:grid-cols-[0.94fr_1.06fr]">
        <section className="panel mesh-bg relative overflow-hidden px-6 py-8 md:px-8 md:py-10">
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950/15 via-slate-950/55 to-slate-950/90" />
          <div className="relative z-10">
            <span className="pill bg-white/10 text-white">{eyebrow}</span>
            <h1 className="mt-5 text-4xl text-white md:text-5xl">{title}</h1>
            <p className="mt-4 max-w-xl text-base leading-8 text-slate-200/90">{description}</p>

            <div className="mt-8 rounded-[28px] border border-white/10 bg-slate-950/45 p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/20 text-brand-100">
                  <Sparkles size={20} />
                </div>
                <div>
                  <p className="font-semibold text-white">{asideTitle}</p>
                  <p className="mt-1 text-sm text-slate-300">{asideText}</p>
                </div>
              </div>

              <div className="mt-6 space-y-3">
                {defaultHighlights.map((item) => (
                  <div
                    key={item}
                    className="flex items-start gap-3 rounded-[22px] border border-white/10 bg-white/[0.04] px-4 py-3"
                  >
                    <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-400/15 text-emerald-200">
                      <ShieldCheck size={16} />
                    </div>
                    <p className="text-sm leading-6 text-slate-200">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="panel-soft rounded-[32px] p-5 md:p-7">{children}</section>
      </div>
    </div>
  )
}
