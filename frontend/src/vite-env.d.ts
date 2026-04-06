/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_TELEGRAM_BOT_URL?: string
  readonly VITE_MANAGER_TELEGRAM_URL?: string
  readonly VITE_SUPPORT_VK_URL?: string
  readonly VITE_SUPPORT_MAX_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
