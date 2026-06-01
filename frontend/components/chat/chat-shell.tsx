'use client'

import { useRef } from 'react'
import type { FormEvent, KeyboardEvent, RefObject } from 'react'
import { ChatSidebar } from './chat-sidebar'
import { ChatTopbar } from './chat-topbar'
import { ChatComposer } from './chat-composer'
import { MessageList } from './message-list'
import { WelcomeState } from './welcome-state'
import type { ChatUiMessage, SessionListItem, SuggestionCard } from './chat.types'

interface ChatShellProps {
  sessions: SessionListItem[]
  activeSessionId: string | null
  activeSessionTitle: string
  messages: ChatUiMessage[]
  loading: boolean
  input: string
  userEmail: string
  theme: 'light' | 'dark'
  textareaRef: RefObject<HTMLTextAreaElement>
  suggestions: SuggestionCard[]
  onInputChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  onAsk: (question: string) => void
  onCopy: (text: string) => void
  onToggleTheme: () => void
  onLogout: () => void
  onCreateSession: () => void
  onSelectSession: (sessionId: string) => void
  onRenameSession: (sessionId: string) => void
  onDeleteSession: (sessionId: string) => void
  onExportSession: (sessionId: string) => void
  /**
   * Optional ref for the scroll-anchor at the bottom of the message thread.
   * When provided, the page may call anchorRef.current.scrollIntoView() after
   * new messages arrive. If omitted, MessageList scrolls internally via useEffect.
   */
  messagesEndRef?: RefObject<HTMLDivElement>
  onToggleSidebar?: () => void
}

export function ChatShell(props: ChatShellProps) {
  const hasMessages = props.messages.length > 0

  return (
    <div className="chat-layout">
      <ChatSidebar
        sessions={props.sessions}
        activeSessionId={props.activeSessionId}
        onSelect={props.onSelectSession}
        onCreate={props.onCreateSession}
        onRename={props.onRenameSession}
        onDelete={props.onDeleteSession}
        onExport={props.onExportSession}
      />

      <div className="chat-main">
        <ChatTopbar
          title={props.activeSessionTitle}
          theme={props.theme}
          userEmail={props.userEmail}
          onMobileMenuToggle={props.onToggleSidebar}
          onToggleTheme={props.onToggleTheme}
          onLogout={props.onLogout}
        />

        <main className="chat-content">
          {hasMessages ? (
            <MessageList
            messages={props.messages}
            loading={props.loading}
            onCopy={props.onCopy}
            messagesEndRef={props.messagesEndRef}
          />
          ) : (
            <WelcomeState suggestions={props.suggestions} onAsk={props.onAsk} />
          )}
        </main>

        <ChatComposer
          input={props.input}
          loading={props.loading}
          textareaRef={props.textareaRef}
          onChange={props.onInputChange}
          onSubmit={props.onSubmit}
          onKeyDown={props.onKeyDown}
        />
      </div>
    </div>
  )
}