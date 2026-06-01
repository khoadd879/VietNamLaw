/**
 * Shared frontend chat UI types.
 * These are consumed by page orchestration, the chat shell,
 * and individual presentational components.
 */

export interface ChatUiMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
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
