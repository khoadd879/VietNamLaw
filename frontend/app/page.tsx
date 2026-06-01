'use client'

import { useState, useRef, useEffect, FormEvent, KeyboardEvent } from 'react'
import { useRouter } from 'next/navigation'
import {
  clearAuthState,
  isLoggedIn,
  isNotFoundError,
  isUnauthorizedError,
  createSession,
  deleteSession,
  getMessages,
  getSession,
  listSessions,
  mapMessageHistory,
  renameSession,
  sendAuthedMessage,
  getStoredSessionId,
  setStoredSessionId,
  clearStoredSessionId,
} from '@/lib/api'
import { ChatSidebar } from '@/components/chat/chat-sidebar'
import { ChatTopbar } from '@/components/chat/chat-topbar'
import { ChatComposer } from '@/components/chat/chat-composer'
import { MessageList } from '@/components/chat/message-list'
import { WelcomeState } from '@/components/chat/welcome-state'
import { downloadSessionMarkdown } from '@/components/chat/session-export'
import type { ChatUiMessage, SessionListItem, SuggestionCard } from '@/components/chat/chat.types'

const SUGGESTIONS: SuggestionCard[] = [
  {
    title: '👨‍👩‍👧 Hôn nhân & Gia đình',
    desc: 'Ly hôn, quyền nuôi con, chia tài sản',
    q: 'Thủ tục ly hôn đơn phương cần chuẩn bị những gì?',
  },
  {
    title: '🏢 Doanh nghiệp',
    desc: 'Thành lập, giải thể, quản trị công ty',
    q: 'Công ty TNHH và CTCP khác nhau như thế nào?',
  },
  {
    title: '⚡ Lao động',
    desc: 'Hợp đồng, sa thải, lương thưởng, BHXH',
    q: 'Người lao động bị sa thải trái luật được bồi thường như thế nào?',
  },
  {
    title: '🏠 Đất đai & Nhà ở',
    desc: 'Sổ đỏ, tranh chấp, chuyển nhượng',
    q: 'Tranh chấp đất đai với hàng xóm phải làm gì?',
  },
]

const DEFAULT_TITLE = 'Cuộc tư vấn pháp lý'

export default function Home() {
  const router = useRouter()

  // ── State ────────────────────────────────────────────────
  const [messages, setMessages] = useState<ChatUiMessage[]>([])
  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeSessionTitle, setActiveSessionTitle] = useState(DEFAULT_TITLE)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // ── Auth guard & theme bootstrap ─────────────────────────
  useEffect(() => {
    const saved = localStorage.getItem('lexvn-theme') as 'light' | 'dark' | null
    if (saved) {
      setTheme(saved)
      document.documentElement.setAttribute('data-theme', saved)
    }

    if (!isLoggedIn()) {
      router.replace('/auth')
      return
    }

    hydrateSessions(null)
  }, [router])

  // ── Auto-scroll ──────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── Session hydration ────────────────────────────────────
  async function hydrateSessions(targetSessionId: string | null) {
    let allSessions: Awaited<ReturnType<typeof listSessions>> = []
    try {
      allSessions = await listSessions()
    } catch {
      // No sessions yet — this is fine
      allSessions = []
    }

    setSessions(
      allSessions.map((s) => ({
        id: s.id,
        title: s.title || DEFAULT_TITLE,
        preview: 'Mở để xem nội dung',
        updatedLabel: 'Phiên đã lưu',
      })),
    )

    // Resolve which session to load
    const resolved =
      targetSessionId || getStoredSessionId() || allSessions[0]?.id || null

    if (!resolved) {
      setActiveSessionId(null)
      setMessages([])
      setActiveSessionTitle(DEFAULT_TITLE)
      return
    }

    setStoredSessionId(resolved)
    setActiveSessionId(resolved)

    try {
      const [session, sessionMessages] = await Promise.all([
        getSession(resolved),
        getMessages(resolved),
      ])
      setActiveSessionTitle(session.title || DEFAULT_TITLE)
      setMessages(mapMessageHistory(sessionMessages))
    } catch {
      // Session may have been deleted; fall back to empty
      setActiveSessionId(null)
      setMessages([])
      setActiveSessionTitle(DEFAULT_TITLE)
      clearStoredSessionId()
    }
  }

  // ── Create new session ────────────────────────────────────
  async function handleCreateSession() {
    try {
      const session = await createSession('Cuộc tư vấn mới')
      setStoredSessionId(session.id)
      await hydrateSessions(session.id)
    } catch {
      // Silently fail; user can retry
    }
  }

  // ── Select existing session ──────────────────────────────
  async function handleSelectSession(sessionId: string) {
    setMobileSidebarOpen(false)
    await hydrateSessions(sessionId)
  }

  // ── Rename session ───────────────────────────────────────
  async function handleRenameSession(sessionId: string) {
    const current = sessions.find((s) => s.id === sessionId)
    const next = window.prompt('Nhập tên mới cho phiên tư vấn:', current?.title ?? '')
    if (!next?.trim()) return
    try {
      await renameSession(sessionId, next.trim())
      await hydrateSessions(sessionId)
    } catch {
      // Silently fail
    }
  }

  // ── Delete session ───────────────────────────────────────
  async function handleDeleteSession(sessionId: string) {
    const confirmed = window.confirm('Xóa phiên tư vấn này? Hành động này không thể hoàn tác.')
    if (!confirmed) return
    try {
      await deleteSession(sessionId)
    } catch {
      // Continue even if the delete call fails
    }
    if (activeSessionId === sessionId) {
      clearStoredSessionId()
    }
    await hydrateSessions(null)
  }

  // ── Export session to .md ────────────────────────────────
  async function handleExportSession(sessionId: string) {
    if (sessionId !== activeSessionId) {
      // Load the session's messages before exporting
      try {
        const msgs = await getMessages(sessionId)
        const session = await getSession(sessionId)
        const uiMsgs = mapMessageHistory(msgs)
        downloadSessionMarkdown(session.title || DEFAULT_TITLE, uiMsgs)
        return
      } catch {
        return
      }
    }
    downloadSessionMarkdown(activeSessionTitle, messages)
  }

  // ── Copy text to clipboard ────────────────────────────────
  async function handleCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard API may not be available in some contexts
    }
  }

  // ── Submit a message ─────────────────────────────────────
  async function submitMessage(text: string) {
    if (!text.trim() || loading) return

    if (!isLoggedIn()) {
      router.replace('/auth')
      return
    }

    const userMsg: ChatUiMessage = { role: 'user', content: text.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setLoading(true)

    try {
      const res = await sendAuthedMessage(text.trim())
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.reply, sources: res.sources },
      ])

      // Refresh sessions so the sidebar reflects the new activity
      hydrateSessions(activeSessionId).catch(() => undefined)
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthState()
        router.replace('/auth')
        return
      }

      if (isNotFoundError(error)) {
        try {
          const res = await sendAuthedMessage(text.trim())
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: res.reply, sources: res.sources },
          ])
          return
        } catch {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: '⚠️ Không thể khôi phục phiên chat. Vui lòng thử lại.',
            },
          ])
          return
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ Không thể kết nối. Vui lòng thử lại.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  // ── Form handlers ────────────────────────────────────────
  function handleFormSubmit(e: FormEvent) {
    e.preventDefault()
    submitMessage(input)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submitMessage(input)
    }
  }

  function handleInputChange(value: string) {
    setInput(value)
    // Auto-resize textarea
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'
    }
  }

  // ── Theme toggle ──────────────────────────────────────────
  function handleToggleTheme() {
    const next: 'light' | 'dark' = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('lexvn-theme', next)
  }

  // ── Logout ────────────────────────────────────────────────
  function handleLogout() {
    clearAuthState()
    router.replace('/auth')
  }

  const userEmail =
    typeof window !== 'undefined'
      ? localStorage.getItem('lexvn-user-email') || 'Tài khoản LexVN'
      : 'Tài khoản LexVN'

  const hasMessages = messages.length > 0

  return (
    <div className="chat-layout">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={handleSelectSession}
        onCreate={handleCreateSession}
        onRename={handleRenameSession}
        onDelete={handleDeleteSession}
        onExport={handleExportSession}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />

      <div className="chat-main">
        <ChatTopbar
          title={activeSessionTitle}
          theme={theme}
          userEmail={userEmail}
          onMobileMenuToggle={() => setMobileSidebarOpen((v) => !v)}
          onToggleTheme={handleToggleTheme}
          onLogout={handleLogout}
        />

        <main className="chat-content">
          {hasMessages ? (
            <MessageList messages={messages} loading={loading} onCopy={handleCopy} />
          ) : (
            <WelcomeState suggestions={SUGGESTIONS} onAsk={submitMessage} />
          )}
          <div ref={messagesEndRef} />
        </main>

        <ChatComposer
          input={input}
          loading={loading}
          textareaRef={textareaRef}
          onChange={handleInputChange}
          onSubmit={handleFormSubmit}
          onKeyDown={handleKeyDown}
        />
      </div>
    </div>
  )
}