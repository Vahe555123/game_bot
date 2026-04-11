export type HelpContentSection = {
  title: string
  body: string
}

export type HelpContentFaqItem = {
  question: string
  answer: string
}

export type HelpSocialLink = {
  label: string
  url: string
}

export type HelpContent = {
  eyebrow: string
  title: string
  subtitle: string
  support_title: string
  support_description: string
  support_button_label: string
  support_button_url?: string | null
  purchases_title: string
  purchases_description: string
  purchases_button_label: string
  purchases_button_url?: string | null
  social_links: HelpSocialLink[]
  sections: HelpContentSection[]
  faq_items: HelpContentFaqItem[]
  updated_at?: string | null
}

export type HelpContentPayload = Omit<HelpContent, 'updated_at'>
