import type { HelpContent } from '../types/help'
import { apiClient } from './api'

export async function fetchHelpContent() {
  const response = await apiClient.get<HelpContent>('/site/content/help')
  return response.data
}
