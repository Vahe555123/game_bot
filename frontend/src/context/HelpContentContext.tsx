import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchHelpContent } from '../services/help'
import type { HelpContent, HelpSocialLink } from '../types/help'
import { getApiErrorMessage } from '../utils/apiErrors'

type QuestionSupportLink = {
  label: 'ВКонтакте' | 'Телеграм' | 'Max'
  url: string
}

type HelpContentContextValue = {
  content: HelpContent
  error: string | null
  isLoading: boolean
  questionSupportLinks: QuestionSupportLink[]
  refreshHelpContent: () => Promise<void>
  setHelpContent: (content: HelpContent) => void
}

const HelpContentContext = createContext<HelpContentContextValue | null>(null)

function buildFallbackHelpContent(): HelpContent {
  const supportUrl = import.meta.env.VITE_MANAGER_TELEGRAM_URL || import.meta.env.VITE_TELEGRAM_BOT_URL || null
  const supportVkUrl = import.meta.env.VITE_SUPPORT_VK_URL || null
  const supportMaxUrl = import.meta.env.VITE_SUPPORT_MAX_URL || null

  return {
    eyebrow: 'Помощь',
    title: 'Помощь по покупкам и доступу к заказам',
    subtitle:
      'Здесь собраны ответы по оплате, истории заказов и связи с менеджером. Если вопрос срочный, откройте поддержку и напишите нам напрямую.',
    support_title: 'Нужна помощь менеджера?',
    support_description:
      'Если не нашли покупку, не открывается доступ или нужна консультация по региону и подписке, напишите нам напрямую.',
    support_button_label: 'Написать менеджеру',
    support_button_url: supportUrl,
    purchases_title: 'Где посмотреть мои покупки',
    purchases_description:
      'История заказов и переписка по ним доступны на oplata.info. Используйте тот же email, который указан как email для покупок.',
    purchases_button_label: 'Открыть oplata.info',
    purchases_button_url: 'https://oplata.info',
    social_links: [
      supportVkUrl ? { label: 'ВКонтакте', url: supportVkUrl } : null,
      supportUrl ? { label: 'Телеграм', url: supportUrl } : null,
      supportMaxUrl ? { label: 'Max', url: supportMaxUrl } : null,
    ].filter((link): link is HelpSocialLink => Boolean(link?.url)),
    sections: [
      {
        title: 'Как оформить заказ',
        body: 'Выберите товар, проверьте регион и завершите оплату. Все новые покупки будут привязаны к email для покупок.',
      },
      {
        title: 'Как найти уже оплаченный заказ',
        body: 'Откройте oplata.info, войдите по email для покупок и найдите нужный заказ в истории.',
      },
      {
        title: 'Когда писать в поддержку',
        body: 'Если после оплаты появилась ошибка, не пришёл код или нужен совет по региону, сразу напишите менеджеру.',
      },
    ],
    faq_items: [
      {
        question: 'Где посмотреть мои покупки?',
        answer: 'Перейдите на oplata.info и используйте email для покупок, чтобы открыть историю заказов.',
      },
      {
        question: 'Что делать, если после оплаты появилась ошибка?',
        answer: 'Проверьте почту и папку спам, затем откройте oplata.info. Если заказ всё ещё недоступен, свяжитесь с менеджером.',
      },
      {
        question: 'Какой email использовать для заказов?',
        answer: 'Указывайте рабочий email для покупок. К нему привязываются все новые заказы и уведомления.',
      },
    ],
    updated_at: null,
  }
}

function resolveSupportChannel(link: HelpSocialLink) {
  const label = link.label.trim().toLowerCase()
  const url = link.url.trim().toLowerCase()

  if (label.includes('вконт') || label === 'vk' || url.includes('vk.com')) {
    return 'vk'
  }

  if (label.includes('телег') || label.includes('telegram') || url.includes('t.me') || url.includes('telegram.me')) {
    return 'telegram'
  }

  if (label === 'max' || url.includes('max.ru') || url.includes('max.com')) {
    return 'max'
  }

  return null
}

function buildQuestionSupportLinks(content: HelpContent): QuestionSupportLink[] {
  const linksByChannel = new Map<QuestionSupportLink['label'], string>()

  content.social_links.forEach((link) => {
    const channel = resolveSupportChannel(link)
    if (channel === 'vk' && !linksByChannel.has('ВКонтакте')) {
      linksByChannel.set('ВКонтакте', link.url)
    }
    if (channel === 'telegram' && !linksByChannel.has('Телеграм')) {
      linksByChannel.set('Телеграм', link.url)
    }
    if (channel === 'max' && !linksByChannel.has('Max')) {
      linksByChannel.set('Max', link.url)
    }
  })

  if (!linksByChannel.has('Телеграм') && content.support_button_url) {
    const supportUrl = content.support_button_url.trim()
    if (supportUrl.includes('t.me') || supportUrl.includes('telegram.me')) {
      linksByChannel.set('Телеграм', supportUrl)
    }
  }

  return ['ВКонтакте', 'Телеграм', 'Max']
    .map((label) => {
      const url = linksByChannel.get(label as QuestionSupportLink['label'])
      return url ? { label: label as QuestionSupportLink['label'], url } : null
    })
    .filter((link): link is QuestionSupportLink => Boolean(link))
}

export function HelpContentProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<HelpContent>(() => buildFallbackHelpContent())
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshHelpContent = useCallback(async () => {
    setIsLoading(true)

    try {
      const response = await fetchHelpContent()
      setContent(response)
      setError(null)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'Не удалось загрузить страницу помощи.'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshHelpContent()
  }, [refreshHelpContent])

  const value = useMemo<HelpContentContextValue>(
    () => ({
      content,
      error,
      isLoading,
      questionSupportLinks: buildQuestionSupportLinks(content),
      refreshHelpContent,
      setHelpContent: (nextContent) => {
        setContent(nextContent)
        setError(null)
      },
    }),
    [content, error, isLoading, refreshHelpContent],
  )

  return <HelpContentContext.Provider value={value}>{children}</HelpContentContext.Provider>
}

export function useHelpContent() {
  const context = useContext(HelpContentContext)

  if (!context) {
    throw new Error('useHelpContent must be used within HelpContentProvider')
  }

  return context
}
