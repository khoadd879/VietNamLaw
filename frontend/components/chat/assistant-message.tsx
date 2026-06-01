'use client'

import { LawyerResponseView } from './lawyer-response-view'
import type { ChatUiMessage } from './chat.types'

interface AssistantMessageProps {
  message: ChatUiMessage
  onCopy: (text: string) => void
  onSelectFollowUp?: (q: string) => void
}

export function AssistantMessage({ message, onCopy, onSelectFollowUp }: AssistantMessageProps) {
  // Defensive: message.structured can be null/undefined (LLM fallback path,
  // or legacy messages saved before Sprint 1). Treat it as missing and show
  // plain text rather than crashing.
  const s = message.structured
  const hasStructured = Boolean(
    s && (s.loi_chao || s.tom_tat_vu_viec || s.phan_tich_phap_ly)
  )

  return (
    <article className="message-row">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        Lx
      </div>
      <div className="message-card message-card--assistant">
        {hasStructured && s ? (
          <LawyerResponseView section={s} sources={message.sources} onSelectFollowUp={onSelectFollowUp} />
        ) : (
          <pre className="message-fallback-text">{message.content}</pre>
        )}

        <div className="message-actions">
          <button
            type="button"
            className="message-action"
            onClick={() => onCopy(message.content)}
            title="Sao chép nội dung"
          >
            Sao chép
          </button>
        </div>
      </div>
    </article>
  )
}
