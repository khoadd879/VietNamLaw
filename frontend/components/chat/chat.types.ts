/**
 * Shared frontend chat UI types.
 * These are consumed by page orchestration, the chat shell,
 * and individual presentational components.
 */

import type { LawyerSection } from '@/lib/api'

export interface ChatUiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  structured?: LawyerSection | null
  createdAt: string
}

export interface SessionListItem {
  id: string
  title: string
  preview: string
  updatedLabel: string
}

export interface SuggestionCard {
  title: string
  desc: string
  q: string
}
