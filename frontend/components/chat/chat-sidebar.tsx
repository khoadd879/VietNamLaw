'use client'

import type { SessionListItem } from './chat.types'

interface ChatSidebarProps {
  sessions: SessionListItem[]
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
  onCreate: () => void
  onRename: (sessionId: string) => void
  onDelete: (sessionId: string) => void
  onExport: (sessionId: string) => void
  mobileOpen?: boolean
  onMobileClose?: () => void
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onExport,
  mobileOpen = false,
  onMobileClose,
}: ChatSidebarProps) {
  return (
    <>
      {mobileOpen && onMobileClose && (
        <div
          className="chat-sidebar__overlay"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      <aside className={`chat-sidebar${mobileOpen ? ' is-open' : ''}`}>
        <div className="chat-sidebar__header">
          <div className="chat-sidebar__brand">
            <div className="chat-brand-logo">Lx</div>
            <div className="chat-brand-text">
              <div className="chat-brand-name">LexVN</div>
              <div className="chat-brand-tagline">Luật sư AI · Việt Nam</div>
            </div>
          </div>
          <button
            type="button"
            className="chat-new-btn"
            onClick={onCreate}
          >
            <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24" aria-hidden="true">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Cuộc tư vấn mới
          </button>
        </div>

        <div className="chat-sidebar__list">
          {sessions.length === 0 ? (
            <p className="chat-sidebar__empty">Chưa có phiên tư vấn nào.</p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item${session.id === activeSessionId ? ' session-item--active' : ''}`}
              >
                <button
                  type="button"
                  className="session-item__select"
                  onClick={() => onSelect(session.id)}
                >
                  <span className="session-item__title">{session.title}</span>
                  <span className="session-item__preview">{session.preview}</span>
                  <span className="session-item__meta">{session.updatedLabel}</span>
                </button>
                <div className="session-item__actions">
                  <button type="button" onClick={() => onRename(session.id)}>
                    Đổi tên
                  </button>
                  <button type="button" onClick={() => onExport(session.id)}>
                    Xuất MD
                  </button>
                  <button
                    type="button"
                    className="session-item__delete"
                    onClick={() => onDelete(session.id)}
                  >
                    Xóa
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  )
}
