import { Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { fetchAdminHelpContent, updateAdminHelpContent } from '../../services/admin'
import type { AdminHelpContent, AdminHelpContentPayload } from '../../types/admin'
import type { HelpContentFaqItem, HelpContentSection, HelpSocialLink } from '../../types/help'
import { getApiErrorMessage } from '../../utils/apiErrors'
import {
  AdminNotice,
  AdminSectionCard,
  EMPTY_ADMIN_NOTICE,
  formatDateTime,
  type AdminNoticeState,
} from './AdminCommon'

const EMPTY_SECTION: HelpContentSection = {
  title: '',
  body: '',
}

const EMPTY_FAQ: HelpContentFaqItem = {
  question: '',
  answer: '',
}

const EMPTY_SOCIAL_LINK: HelpSocialLink = {
  label: '',
  url: '',
}

const EMPTY_FORM: AdminHelpContentPayload = {
  eyebrow: 'Помощь',
  title: '',
  subtitle: '',
  support_title: '',
  support_description: '',
  support_button_label: '',
  support_button_url: '',
  purchases_title: '',
  purchases_description: '',
  purchases_button_label: '',
  purchases_button_url: '',
  social_links: [EMPTY_SOCIAL_LINK],
  sections: [EMPTY_SECTION],
  faq_items: [EMPTY_FAQ],
}

function buildFormState(content?: AdminHelpContent | null): AdminHelpContentPayload {
  if (!content) {
    return EMPTY_FORM
  }

  return {
    eyebrow: content.eyebrow,
    title: content.title,
    subtitle: content.subtitle,
    support_title: content.support_title,
    support_description: content.support_description,
    support_button_label: content.support_button_label,
    support_button_url: content.support_button_url ?? '',
    purchases_title: content.purchases_title,
    purchases_description: content.purchases_description,
    purchases_button_label: content.purchases_button_label,
    purchases_button_url: content.purchases_button_url ?? '',
    social_links: content.social_links?.length ? content.social_links : [EMPTY_SOCIAL_LINK],
    sections: content.sections.length ? content.sections : [EMPTY_SECTION],
    faq_items: content.faq_items.length ? content.faq_items : [EMPTY_FAQ],
  }
}

function buildEmptySection(): HelpContentSection {
  return { ...EMPTY_SECTION }
}

function buildEmptyFaq(): HelpContentFaqItem {
  return { ...EMPTY_FAQ }
}

function buildEmptySocialLink(): HelpSocialLink {
  return { ...EMPTY_SOCIAL_LINK }
}

export function AdminContentSection() {
  const [content, setContent] = useState<AdminHelpContent | null>(null)
  const [form, setForm] = useState<AdminHelpContentPayload>(EMPTY_FORM)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [notice, setNotice] = useState<AdminNoticeState>(EMPTY_ADMIN_NOTICE)

  async function loadContent() {
    setIsLoading(true)

    try {
      const response = await fetchAdminHelpContent()
      setContent(response)
      setForm(buildFormState(response))
      setNotice(EMPTY_ADMIN_NOTICE)
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось загрузить страницу помощи.'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadContent()
  }, [])

  function updateField<K extends keyof AdminHelpContentPayload>(field: K, value: AdminHelpContentPayload[K]) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function updateSection(index: number, field: keyof HelpContentSection, value: string) {
    setForm((current) => ({
      ...current,
      sections: current.sections.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    }))
  }

  function updateFaq(index: number, field: keyof HelpContentFaqItem, value: string) {
    setForm((current) => ({
      ...current,
      faq_items: current.faq_items.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    }))
  }

  function updateSocialLink(index: number, field: keyof HelpSocialLink, value: string) {
    setForm((current) => ({
      ...current,
      social_links: current.social_links.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSaving(true)
    setNotice(EMPTY_ADMIN_NOTICE)

    try {
      const payload = {
        ...form,
        social_links: form.social_links.filter((link) => link.label.trim() && link.url.trim()),
      }
      const response = await updateAdminHelpContent(payload)
      setContent(response)
      setForm(buildFormState(response))
      setNotice({ type: 'success', message: 'Страница помощи обновлена.' })
    } catch (error) {
      setNotice({
        type: 'error',
        message: getApiErrorMessage(error, 'Не удалось сохранить страницу помощи.'),
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <AdminSectionCard
      id="admin-content"
      title="Помощь"
      description="Управление публичной страницей помощи: заголовки, кнопки, инструкции и FAQ."
      action={
        <button type="button" className="btn-secondary" onClick={() => loadContent()}>
          <RefreshCw size={16} />
          Обновить
        </button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_320px]">
        <form className="space-y-6" onSubmit={handleSubmit}>
          <AdminNotice state={notice} />

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200">Eyebrow</label>
              <input
                value={form.eyebrow}
                onChange={(event) => updateField('eyebrow', event.target.value)}
                className="auth-input"
                placeholder="Помощь"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200">Заголовок</label>
              <input
                value={form.title}
                onChange={(event) => updateField('title', event.target.value)}
                className="auth-input"
                placeholder="Помощь по покупкам и доступу к заказам"
              />
            </div>

            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-slate-200">Подзаголовок</label>
              <textarea
                value={form.subtitle}
                onChange={(event) => updateField('subtitle', event.target.value)}
                className="auth-input min-h-[120px]"
                placeholder="Коротко объясните, чем полезна страница."
              />
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
              <h3 className="text-xl text-white">Блок поддержки</h3>

              <div className="mt-4 space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Заголовок</label>
                  <input
                    value={form.support_title}
                    onChange={(event) => updateField('support_title', event.target.value)}
                    className="auth-input"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Описание</label>
                  <textarea
                    value={form.support_description}
                    onChange={(event) => updateField('support_description', event.target.value)}
                    className="auth-input min-h-[120px]"
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">Текст кнопки</label>
                    <input
                      value={form.support_button_label}
                      onChange={(event) => updateField('support_button_label', event.target.value)}
                      className="auth-input"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">Ссылка кнопки</label>
                    <input
                      value={form.support_button_url ?? ''}
                      onChange={(event) => updateField('support_button_url', event.target.value)}
                      className="auth-input"
                      placeholder="https://t.me/..."
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
              <h3 className="text-xl text-white">Блок покупок</h3>

              <div className="mt-4 space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Заголовок</label>
                  <input
                    value={form.purchases_title}
                    onChange={(event) => updateField('purchases_title', event.target.value)}
                    className="auth-input"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-200">Описание</label>
                  <textarea
                    value={form.purchases_description}
                    onChange={(event) => updateField('purchases_description', event.target.value)}
                    className="auth-input min-h-[120px]"
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">Текст кнопки</label>
                    <input
                      value={form.purchases_button_label}
                      onChange={(event) => updateField('purchases_button_label', event.target.value)}
                      className="auth-input"
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-200">Ссылка кнопки</label>
                    <input
                      value={form.purchases_button_url ?? ''}
                      onChange={(event) => updateField('purchases_button_url', event.target.value)}
                      className="auth-input"
                      placeholder="https://oplata.info"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-xl text-white">Социальные ссылки</h3>
                <p className="mt-2 text-sm text-slate-400">Кнопки для связи: VK, Max, Telegram и любые другие каналы.</p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setForm((current) => ({ ...current, social_links: [...current.social_links, buildEmptySocialLink()] }))}
              >
                <Plus size={16} />
                Добавить ссылку
              </button>
            </div>

            <div className="mt-5 space-y-4">
              {form.social_links.map((link, index) => (
                <div key={`social-${index}`} className="rounded-[24px] border border-white/10 bg-slate-950/35 p-4">
                  <div className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)_auto]">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-200">Название</label>
                      <input
                        value={link.label}
                        onChange={(event) => updateSocialLink(index, 'label', event.target.value)}
                        className="auth-input"
                        placeholder="VK"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-200">Ссылка</label>
                      <input
                        value={link.url}
                        onChange={(event) => updateSocialLink(index, 'url', event.target.value)}
                        className="auth-input"
                        placeholder="https://vk.com/..."
                      />
                    </div>

                    <div className="md:self-end">
                      <button
                        type="button"
                        className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10"
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            social_links:
                              current.social_links.length > 1
                                ? current.social_links.filter((_, itemIndex) => itemIndex !== index)
                                : [buildEmptySocialLink()],
                          }))
                        }
                      >
                        <Trash2 size={16} />
                        Удалить
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-xl text-white">Инструкции</h3>
                <p className="mt-2 text-sm text-slate-400">Короткие блоки, которые показываются на странице помощи.</p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setForm((current) => ({ ...current, sections: [...current.sections, buildEmptySection()] }))}
              >
                <Plus size={16} />
                Добавить блок
              </button>
            </div>

            <div className="mt-5 space-y-4">
              {form.sections.map((section, index) => (
                <div key={`section-${index}`} className="rounded-[24px] border border-white/10 bg-slate-950/35 p-4">
                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto]">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-200">Заголовок блока</label>
                      <input
                        value={section.title}
                        onChange={(event) => updateSection(index, 'title', event.target.value)}
                        className="auth-input"
                      />
                    </div>

                    <div className="md:self-end">
                      <button
                        type="button"
                        className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10"
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            sections:
                              current.sections.length > 1
                                ? current.sections.filter((_, itemIndex) => itemIndex !== index)
                                : [buildEmptySection()],
                          }))
                        }
                      >
                        <Trash2 size={16} />
                        Удалить
                      </button>
                    </div>
                  </div>

                  <div className="mt-4">
                    <label className="mb-2 block text-sm font-medium text-slate-200">Описание</label>
                    <textarea
                      value={section.body}
                      onChange={(event) => updateSection(index, 'body', event.target.value)}
                      className="auth-input min-h-[120px]"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-xl text-white">FAQ</h3>
                <p className="mt-2 text-sm text-slate-400">Вопросы и ответы, которые раскрываются на публичной странице.</p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setForm((current) => ({ ...current, faq_items: [...current.faq_items, buildEmptyFaq()] }))}
              >
                <Plus size={16} />
                Добавить вопрос
              </button>
            </div>

            <div className="mt-5 space-y-4">
              {form.faq_items.map((item, index) => (
                <div key={`faq-${index}`} className="rounded-[24px] border border-white/10 bg-slate-950/35 p-4">
                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto]">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-200">Вопрос</label>
                      <input
                        value={item.question}
                        onChange={(event) => updateFaq(index, 'question', event.target.value)}
                        className="auth-input"
                      />
                    </div>

                    <div className="md:self-end">
                      <button
                        type="button"
                        className="btn-secondary border-rose-400/20 text-rose-100 hover:bg-rose-500/10"
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            faq_items:
                              current.faq_items.length > 1
                                ? current.faq_items.filter((_, itemIndex) => itemIndex !== index)
                                : [buildEmptyFaq()],
                          }))
                        }
                      >
                        <Trash2 size={16} />
                        Удалить
                      </button>
                    </div>
                  </div>

                  <div className="mt-4">
                    <label className="mb-2 block text-sm font-medium text-slate-200">Ответ</label>
                    <textarea
                      value={item.answer}
                      onChange={(event) => updateFaq(index, 'answer', event.target.value)}
                      className="auth-input min-h-[140px]"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button type="submit" className="btn-primary" disabled={isSaving || isLoading}>
              {isSaving ? 'Сохраняем...' : 'Сохранить страницу помощи'}
            </button>

            <button
              type="button"
              className="btn-secondary"
              onClick={() => setForm(buildFormState(content))}
              disabled={isSaving || isLoading}
            >
              Сбросить изменения
            </button>
          </div>
        </form>

        <aside className="space-y-4 xl:sticky xl:top-28 xl:self-start">
          <div className="panel-soft rounded-[30px] p-5">
            <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Статус</p>
            <h3 className="mt-3 text-2xl text-white">Страница помощи</h3>
            <p className="mt-3 text-sm leading-7 text-slate-400">
              Здесь можно быстро обновить FAQ, CTA-кнопки и инструкции без правки кода.
            </p>

            <div className="mt-5 space-y-3">
              <div className="rounded-[22px] border border-white/10 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
                Инструкций: {form.sections.length}
              </div>
              <div className="rounded-[22px] border border-white/10 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
                Вопросов FAQ: {form.faq_items.length}
              </div>
              <div className="rounded-[22px] border border-white/10 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
                Последнее обновление: {formatDateTime(content?.updated_at)}
              </div>
            </div>
          </div>

          <div className="panel-soft rounded-[30px] p-5">
            <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Подсказка</p>
            <p className="mt-3 text-sm leading-7 text-slate-400">
              В описаниях можно использовать переносы строк. Публичная страница покажет их как отдельные абзацы.
            </p>
          </div>
        </aside>
      </div>

      {isLoading ? <p className="mt-5 text-sm text-slate-500">Загружаем контент страницы помощи…</p> : null}
    </AdminSectionCard>
  )
}
