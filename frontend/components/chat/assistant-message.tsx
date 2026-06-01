'use client'

import { LawyerResponseView } from './lawyer-response-view'
import type { ChatUiMessage } from './chat.types'

interface AssistantMessageProps {
  message: ChatUiMessage
  onCopy: (text: string) => void
}

export function AssistantMessage({ message, onCopy }: AssistantMessageProps) {
  const hasStructured =
    message.structured &&
    (message.structured.loi_chao ||
      message.structured.tom_tat_vu_viec ||
      message.structured.phan_tich_phap_ly)

  return (
    <article className="message-row">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        Lx
      </div>
      <div className="message-card message-card--assistant">
        {hasStructured && message.structured ? (
          <LawyerResponseView section={message.structured} sources={message.sources} />
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
