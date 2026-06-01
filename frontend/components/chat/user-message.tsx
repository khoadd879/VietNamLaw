import type { ChatUiMessage } from './chat.types'

interface UserMessageProps {
  message: ChatUiMessage
}

export function UserMessage({ message }: UserMessageProps) {
  return (
    <article className="message-row message-row--user">
      <div className="message-avatar message-avatar--user" aria-hidden="true">
        Bạn
      </div>
      <div className="message-card message-card--user">
        {message.content}
      </div>
    </article>
  )
}
