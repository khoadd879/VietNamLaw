'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatUiMessage } from './chat.types'

interface AssistantMessageProps {
  message: ChatUiMessage
  onCopy: (text: string) => void
}

export function AssistantMessage({ message, onCopy }: AssistantMessageProps) {
  return (
    <article className="message-row">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        Lx
      </div>
      <div className="message-card message-card--assistant">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.content}
        </ReactMarkdown>

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

        {message.sources && message.sources.length > 0 && (
          <div className="message-sources" aria-label="Nguồn tham khảo">
            {message.sources.map((source) => (
              <span key={source} className="message-source-chip">
                {source}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}
