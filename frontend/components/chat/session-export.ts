/**
 * Session Markdown export builder.
 * Produces a formatted .md file from the active session data.
 */
import type { ChatUiMessage } from './chat.types'

/**
 * Build a Markdown representation of a chat session.
 * Used for the "export to .md" action in the sidebar.
 */
export function buildSessionMarkdown(
  title: string,
  messages: ChatUiMessage[],
): string {
  const safeTitle = title.trim() || 'Cuộc tư vấn pháp lý'
  const lines: string[] = [`# ${safeTitle}`, '']

  for (const message of messages) {
    const heading = message.role === 'user' ? '## Người dùng' : '## LexVN'
    lines.push(heading, '', message.content.trim(), '')

    if (message.role === 'assistant' && message.sources?.length) {
      lines.push('### Nguồn', '')
      for (const source of message.sources) {
        lines.push(`- ${source}`)
      }
      lines.push('')
    }
  }

  return lines.join('\n').trim() + '\n'
}

/**
 * Trigger a browser download of session content as a .md file.
 */
export function downloadSessionMarkdown(
  title: string,
  messages: ChatUiMessage[],
): void {
  const content = buildSessionMarkdown(title, messages)
  const safeName = (title.trim() || 'lexvn-session')
    .replace(/[^a-zA-Z0-9À-ɏ\s-]/g, '')
    .slice(0, 60)
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeName}.md`
  link.click()
  URL.revokeObjectURL(url)
}
