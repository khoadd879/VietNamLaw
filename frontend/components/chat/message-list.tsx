'use client'

import { useEffect, useRef } from 'react'
import type { ChatUiMessage } from './chat.types'
import { AssistantMessage } from './assistant-message'
import { UserMessage } from './user-message'

interface MessageListProps {
  messages: ChatUiMessage[]
  loading: boolean
  onCopy: (text: string) => void
  /**
   * Optional external ref for the scroll-anchor at the bottom.
   * When provided, the parent controls scrollIntoView() and this component
   * renders the anchor div with ref attached (internal useEffect is skipped).
   * When omitted, MessageList auto-scrolls via internal useEffect.
   */
  messagesEndRef?: React.RefObject<HTMLDivElement>
}

export function MessageList({
  messages,
  loading,
  onCopy,
  messagesEndRef,
}: MessageListProps) {
  // Internal anchor — used when no external ref is provided.
  const internalAnchorRef = useRef<HTMLDivElement>(null)
  const anchorRef = messagesEndRef ?? internalAnchorRef

  // Auto-scroll: runs whenever messages or loading change.
  // Skipped if the page passed an external messagesEndRef, so the page
  // can control timing itself (e.g. after a state update completes).
  useEffect(() => {
    if (!messagesEndRef) {
      anchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [messages, loading, anchorRef, messagesEndRef])

  return (
    <div className="chat-thread" role="log" aria-live="polite" aria-label="Cuộc hội thoại">
      {messages.map((message, index) =>
        message.role === 'assistant' ? (
          <AssistantMessage key={index} message={message} onCopy={onCopy} />
        ) : (
          <UserMessage key={index} message={message} />
        ),
      )}

      {loading && (
        <div className="message-row">
          <div className="message-avatar message-avatar--assistant" aria-hidden="true">
            Lx
          </div>
          <div className="message-card message-card--assistant">
            <div className="typing-dots" aria-label="Đang trả lời…">
              <span />
              <span />
              <span />
            </div>
          </div>
        </div>
      )}

      {/* Scroll anchor — always rendered; its ref is wired to anchorRef.
          The page can call anchorRef.current.scrollIntoView() after
          state updates if it needs tighter control. */}
      <div ref={anchorRef} style={{ height: 1 }} aria-hidden />
    </div>
  )
}
