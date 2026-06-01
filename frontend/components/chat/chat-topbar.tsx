'use client'

import type { SessionListItem } from './chat.types'
import { ProfileMenu } from './profile-menu'

interface ChatTopbarProps {
  title: string
  theme: 'light' | 'dark'
  userEmail: string
  /** Session list — accepted for future topbar session-count indicator; currently unused in presentational rendering. */
  sessions?: SessionListItem[]
  /** Active session ID — accepted for future topbar state; currently unused in presentational rendering. */
  activeSessionId?: string | null
  onMobileMenuToggle?: () => void
  onToggleTheme: () => void
  onLogout: () => void
}

export function ChatTopbar({
  title,
  theme,
  userEmail,
  sessions: _sessions,
  activeSessionId: _activeSessionId,
  onMobileMenuToggle,
  onToggleTheme,
  onLogout,
}: ChatTopbarProps) {
  return (
    <header className="chat-topbar">
      {onMobileMenuToggle && (
        <button
          type="button"
          className="chat-topbar__menu-btn"
          onClick={onMobileMenuToggle}
          aria-label="Mở danh sách phiên"
        >
        <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
        </button>
      )}

      <div className="chat-topbar__session-info">
        <div className="chat-topbar__live-dot" aria-hidden="true" />
        <span className="chat-topbar__title">{title}</span>
      </div>

      <div className="chat-topbar__actions">
        <ProfileMenu
          email={userEmail}
          theme={theme}
          onToggleTheme={onToggleTheme}
          onLogout={onLogout}
        />
      </div>
    </header>
  )
}
