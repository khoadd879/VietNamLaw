# LexVN UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the LexVN frontend into a multi-session editorial-luxury workspace with reusable UI modules, session sidebar, copy/export actions, and a refined auth experience.

**Architecture:** Move page-level inline styling and monolithic JSX out of `frontend/app/page.tsx` and `frontend/app/auth/page.tsx` into shared components plus a shared token stylesheet. Keep the existing API contract in `frontend/lib/api.ts`, add only frontend orchestration for sessions/export/copy, and preserve all current auth/chat behaviors while improving layout and responsiveness.

**Tech Stack:** Next.js 14, React 18, TypeScript, next/font, existing fetch-based API client, CSS Modules or global CSS via `app/globals.css`, MagicPath for external design components

---

## File structure map

### Existing files to modify
- `frontend/app/layout.tsx` — import shared global stylesheet once, keep font setup and theme bootstrapping
- `frontend/app/page.tsx` — replace inline monolith with composed chat shell and state orchestration
- `frontend/app/auth/page.tsx` — replace inline monolith with composed auth shell and preserved auth logic
- `frontend/lib/api.ts` — add small helpers for session list shaping and message export if needed, but keep API surface compatible
- `frontend/components/theme-script.ts` — keep as-is unless a tiny theme bootstrapping tweak becomes necessary

### New files to create
- `frontend/app/globals.css` — shared tokens, base element reset, typography variables, utility classes for app shells
- `frontend/components/chat/chat-shell.tsx` — top-level presentational chat layout
- `frontend/components/chat/chat-sidebar.tsx` — session list, new chat action, rename/delete/export affordances
- `frontend/components/chat/chat-topbar.tsx` — current session title, theme toggle, profile dropdown trigger, mobile sidebar toggle
- `frontend/components/chat/welcome-state.tsx` — editorial empty state and suggestion cards
- `frontend/components/chat/message-list.tsx` — message loop and typing indicator composition
- `frontend/components/chat/assistant-message.tsx` — assistant bubble with markdown, copy, sources
- `frontend/components/chat/user-message.tsx` — user bubble
- `frontend/components/chat/chat-composer.tsx` — textarea, send button, disclaimer, key handling props
- `frontend/components/chat/profile-menu.tsx` — email display, theme, logout actions
- `frontend/components/chat/session-export.ts` — Markdown export builder from session/message data
- `frontend/components/chat/chat.types.ts` — shared chat UI types
- `frontend/components/auth/auth-shell.tsx` — layout wrapper for auth page
- `frontend/components/auth/auth-hero.tsx` — editorial hero panel
- `frontend/components/auth/auth-panel.tsx` — login/register form presentation

### Tests to create
- `frontend/lib/session-export.test.ts` — export formatting coverage if repository already supports TS test runner; otherwise defer to manual verification in this plan
- Because this project currently has no frontend test harness, implementation should avoid inventing one during redesign. Verification will be done with `npm run lint`, manual browser checks, and focused helper-function tests only if a lightweight existing path exists.

## Task 1: Establish shared visual foundation

**Files:**
- Create: `frontend/app/globals.css`
- Modify: `frontend/app/layout.tsx:1-44`

- [ ] **Step 1: Read the current layout file and identify what must stay**

Keep these behaviors intact:

```tsx
export const metadata: Metadata = {
  title: 'LexVN — Luật sư AI Việt Nam',
  description: 'Tư vấn pháp luật Việt Nam bằng AI',
  icons: {
    icon: '/icon.svg',
  },
}
```

And keep these font/theme hooks intact:

```tsx
const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['400', '600'],
  variable: '--font-display',
})

const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600'],
  variable: '--font-body',
})
```

- [ ] **Step 2: Create the shared stylesheet with tokens and base structure**

Write `frontend/app/globals.css` with the shared design language:

```css
:root {
  --color-bg: #f6f1e8;
  --color-bg-elevated: #fbf7f0;
  --color-surface: rgba(255, 255, 255, 0.82);
  --color-surface-strong: #ffffff;
  --color-surface-soft: #efe7da;
  --color-text: #1f1811;
  --color-text-muted: #5f5346;
  --color-text-subtle: #988773;
  --color-accent: #b8965a;
  --color-accent-strong: #866739;
  --color-accent-soft: #f2e7d1;
  --color-border: rgba(143, 108, 51, 0.16);
  --color-border-strong: rgba(143, 108, 51, 0.28);
  --color-danger: #9d3b2e;
  --shadow-sm: 0 10px 30px rgba(39, 24, 8, 0.06);
  --shadow-md: 0 20px 50px rgba(39, 24, 8, 0.10);
  --shadow-lg: 0 30px 80px rgba(39, 24, 8, 0.14);
  --radius-sm: 12px;
  --radius-md: 18px;
  --radius-lg: 28px;
  --transition-base: 180ms cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme='dark'] {
  --color-bg: #120f0b;
  --color-bg-elevated: #17130f;
  --color-surface: rgba(28, 22, 16, 0.84);
  --color-surface-strong: #1c1610;
  --color-surface-soft: #241d15;
  --color-text: #eee4d4;
  --color-text-muted: #c7b291;
  --color-text-subtle: #7a6a55;
  --color-accent: #c39b59;
  --color-accent-strong: #e0bb79;
  --color-accent-soft: #2a2115;
  --color-border: rgba(195, 155, 89, 0.12);
  --color-border-strong: rgba(195, 155, 89, 0.24);
  --color-danger: #e19386;
  --shadow-sm: 0 10px 30px rgba(0, 0, 0, 0.22);
  --shadow-md: 0 20px 50px rgba(0, 0, 0, 0.32);
  --shadow-lg: 0 30px 80px rgba(0, 0, 0, 0.46);
}

* { box-sizing: border-box; }
html, body { min-height: 100%; }
html { background: var(--color-bg); }
body {
  margin: 0;
  font-family: var(--font-body), sans-serif;
  color: var(--color-text);
  background:
    radial-gradient(circle at top, rgba(184, 150, 90, 0.14), transparent 28%),
    var(--color-bg);
  transition: background var(--transition-base), color var(--transition-base);
}
button, input, textarea { font: inherit; }
a { color: inherit; }
```

- [ ] **Step 3: Import the stylesheet in the root layout**

Update `frontend/app/layout.tsx` to include:

```tsx
import './globals.css'
```

And keep the body minimal:

```tsx
<body className={`${cormorant.variable} ${dmSans.variable}`}>{children}</body>
```

- [ ] **Step 4: Run lint to catch layout/style import issues**

Run: `npm --prefix frontend run lint`
Expected: PASS with no import or JSX errors

- [ ] **Step 5: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/globals.css
git commit -m "feat: add shared frontend design tokens"
```

### Task 2: Create reusable chat types and export helper

**Files:**
- Create: `frontend/components/chat/chat.types.ts`
- Create: `frontend/components/chat/session-export.ts`
- Modify: `frontend/lib/api.ts:1-304`

- [ ] **Step 1: Add shared frontend chat types**

Create `frontend/components/chat/chat.types.ts`:

```ts
export interface ChatUiMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

export interface SessionListItem {
  id: string
  title: string
  preview: string
  updatedLabel: string
}
```

- [ ] **Step 2: Add a Markdown export builder**

Create `frontend/components/chat/session-export.ts`:

```ts
import type { ChatUiMessage } from './chat.types'

export function buildSessionMarkdown(title: string, messages: ChatUiMessage[]): string {
  const safeTitle = title.trim() || 'Cuộc tư vấn pháp lý'
  const lines = [`# ${safeTitle}`, '']

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
```

- [ ] **Step 3: Add a tiny session preview helper in `frontend/lib/api.ts`**

Append this helper near the message mapping utilities:

```ts
export function summarizeSessionPreview(messages: ChatMessage[]): string {
  const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant')
  const lastUser = [...messages].reverse().find((message) => message.role === 'user')
  const basis = lastAssistant?.content || lastUser?.content || 'Chưa có nội dung'
  return basis.replace(/\s+/g, ' ').trim().slice(0, 88)
}
```

- [ ] **Step 4: Run lint to verify helper types compile**

Run: `npm --prefix frontend run lint`
Expected: PASS with no unused import or type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/components/chat/chat.types.ts frontend/components/chat/session-export.ts frontend/lib/api.ts
git commit -m "feat: add chat ui helpers"
```

### Task 3: Build presentational chat components

**Files:**
- Create: `frontend/components/chat/chat-sidebar.tsx`
- Create: `frontend/components/chat/chat-topbar.tsx`
- Create: `frontend/components/chat/welcome-state.tsx`
- Create: `frontend/components/chat/assistant-message.tsx`
- Create: `frontend/components/chat/user-message.tsx`
- Create: `frontend/components/chat/message-list.tsx`
- Create: `frontend/components/chat/chat-composer.tsx`
- Create: `frontend/components/chat/profile-menu.tsx`

- [ ] **Step 1: Create the welcome state component**

Create `frontend/components/chat/welcome-state.tsx`:

```tsx
interface Suggestion {
  title: string
  desc: string
  q: string
}

export function WelcomeState({
  suggestions,
  onAsk,
}: {
  suggestions: Suggestion[]
  onAsk: (question: string) => void
}) {
  return (
    <section className="chat-welcome">
      <div className="chat-welcome__badge">LexVN · Không gian tư vấn pháp lý</div>
      <h1 className="chat-welcome__title">
        Tư duy pháp lý rõ ràng, trong một <em>workspace</em> trang trọng.
      </h1>
      <p className="chat-welcome__copy">
        Trao đổi, lưu vết lập luận, và tiếp tục từng hồ sơ tư vấn với trải nghiệm đọc viết được tối ưu cho nội dung pháp lý.
      </p>
      <div className="chat-welcome__grid">
        {suggestions.map((suggestion) => (
          <button key={suggestion.title} className="chat-prompt-card" onClick={() => onAsk(suggestion.q)}>
            <span className="chat-prompt-card__title">{suggestion.title}</span>
            <span className="chat-prompt-card__desc">{suggestion.desc}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Create the assistant and user bubble components**

Create `frontend/components/chat/assistant-message.tsx`:

```tsx
'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatUiMessage } from './chat.types'

export function AssistantMessage({
  message,
  onCopy,
}: {
  message: ChatUiMessage
  onCopy: (text: string) => void
}) {
  return (
    <article className="message-row">
      <div className="message-avatar message-avatar--assistant">Lx</div>
      <div className="message-card message-card--assistant">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        <div className="message-actions">
          <button type="button" className="message-action" onClick={() => onCopy(message.content)}>
            Sao chép
          </button>
        </div>
        {message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            {message.sources.map((source) => (
              <span key={source} className="message-source-chip">{source}</span>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}
```

Create `frontend/components/chat/user-message.tsx`:

```tsx
import type { ChatUiMessage } from './chat.types'

export function UserMessage({ message }: { message: ChatUiMessage }) {
  return (
    <article className="message-row message-row--user">
      <div className="message-avatar message-avatar--user">Bạn</div>
      <div className="message-card message-card--user">{message.content}</div>
    </article>
  )
}
```

- [ ] **Step 3: Create the list and composer components**

Create `frontend/components/chat/message-list.tsx`:

```tsx
import { AssistantMessage } from './assistant-message'
import { UserMessage } from './user-message'
import type { ChatUiMessage } from './chat.types'

export function MessageList({
  messages,
  loading,
  onCopy,
}: {
  messages: ChatUiMessage[]
  loading: boolean
  onCopy: (text: string) => void
}) {
  return (
    <div className="chat-thread">
      {messages.map((message, index) =>
        message.role === 'assistant' ? (
          <AssistantMessage key={index} message={message} onCopy={onCopy} />
        ) : (
          <UserMessage key={index} message={message} />
        ),
      )}
      {loading && (
        <div className="message-row">
          <div className="message-avatar message-avatar--assistant">Lx</div>
          <div className="message-card message-card--assistant">
            <div className="typing-dots"><span /><span /><span /></div>
          </div>
        </div>
      )}
    </div>
  )
}
```

Create `frontend/components/chat/chat-composer.tsx`:

```tsx
import type { FormEvent, KeyboardEvent, RefObject } from 'react'

export function ChatComposer({
  input,
  loading,
  textareaRef,
  onChange,
  onSubmit,
  onKeyDown,
}: {
  input: string
  loading: boolean
  textareaRef: RefObject<HTMLTextAreaElement>
  onChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}) {
  const canSend = input.trim().length > 0 && !loading

  return (
    <div className="chat-composer-shell">
      <div className="chat-disclaimer">Thông tin tư vấn mang tính tham khảo. Vui lòng tham khảo luật sư có thẩm quyền cho các vấn đề pháp lý quan trọng.</div>
      <form onSubmit={onSubmit} className="chat-composer">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Hỏi bất kỳ vấn đề pháp lý nào…"
          rows={1}
        />
        <button type="submit" disabled={!canSend}>Gửi</button>
      </form>
      <div className="chat-composer-hint">Enter để gửi · Shift+Enter để xuống dòng</div>
    </div>
  )
}
```

- [ ] **Step 4: Create the sidebar and topbar components**

Create `frontend/components/chat/chat-sidebar.tsx`:

```tsx
import type { SessionListItem } from './chat.types'

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  onExport,
}: {
  sessions: SessionListItem[]
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
  onCreate: () => void
  onRename: (sessionId: string) => void
  onDelete: (sessionId: string) => void
  onExport: (sessionId: string) => void
}) {
  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar__header">
        <div>
          <div className="chat-brand">LexVN</div>
          <div className="chat-brand-subtitle">Luật sư AI · Việt Nam</div>
        </div>
        <button type="button" className="chat-primary-button" onClick={onCreate}>Cuộc tư vấn mới</button>
      </div>
      <div className="chat-sidebar__list">
        {sessions.map((session) => (
          <div key={session.id} className={`session-item ${session.id === activeSessionId ? 'session-item--active' : ''}`}>
            <button type="button" className="session-item__select" onClick={() => onSelect(session.id)}>
              <span className="session-item__title">{session.title}</span>
              <span className="session-item__preview">{session.preview}</span>
              <span className="session-item__meta">{session.updatedLabel}</span>
            </button>
            <div className="session-item__actions">
              <button type="button" onClick={() => onRename(session.id)}>Đổi tên</button>
              <button type="button" onClick={() => onDelete(session.id)}>Xóa</button>
              <button type="button" onClick={() => onExport(session.id)}>Xuất MD</button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
```

Create `frontend/components/chat/chat-topbar.tsx` and `frontend/components/chat/profile-menu.tsx` with plain prop-driven rendering; no business logic inside.

- [ ] **Step 5: Run lint to verify all component files compile**

Run: `npm --prefix frontend run lint`
Expected: PASS with no missing imports or prop type errors

- [ ] **Step 6: Commit**

```bash
git add frontend/components/chat
git commit -m "feat: add modular chat components"
```

### Task 4: Compose the chat shell component

**Files:**
- Create: `frontend/components/chat/chat-shell.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Create a pure shell component**

Create `frontend/components/chat/chat-shell.tsx`:

```tsx
import type { FormEvent, KeyboardEvent, RefObject } from 'react'
import { ChatSidebar } from './chat-sidebar'
import { ChatTopbar } from './chat-topbar'
import { ChatComposer } from './chat-composer'
import { MessageList } from './message-list'
import { WelcomeState } from './welcome-state'
import type { ChatUiMessage, SessionListItem } from './chat.types'

interface Suggestion {
  title: string
  desc: string
  q: string
}

export function ChatShell(props: {
  sessions: SessionListItem[]
  activeSessionId: string | null
  activeSessionTitle: string
  messages: ChatUiMessage[]
  loading: boolean
  input: string
  userEmail: string
  theme: 'light' | 'dark'
  textareaRef: RefObject<HTMLTextAreaElement>
  suggestions: Suggestion[]
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
}) {
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
          onToggleTheme={props.onToggleTheme}
          onLogout={props.onLogout}
        />
        <main className="chat-content">
          {hasMessages ? (
            <MessageList messages={props.messages} loading={props.loading} onCopy={props.onCopy} />
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
```

- [ ] **Step 2: Add shell-specific styles to `frontend/app/globals.css`**

Append classes for:

```css
.chat-layout { display: grid; grid-template-columns: 320px minmax(0, 1fr); min-height: 100vh; }
.chat-sidebar { border-right: 1px solid var(--color-border); padding: 24px; background: rgba(255,255,255,0.28); backdrop-filter: blur(18px); }
.chat-main { min-width: 0; display: flex; flex-direction: column; }
.chat-content { flex: 1; min-height: 0; overflow: auto; padding: 32px 40px 16px; }
.chat-thread { max-width: 920px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
.message-row { display: flex; gap: 14px; }
.message-row--user { flex-direction: row-reverse; }
.message-card--assistant { max-width: 760px; }
.message-card--user { max-width: 640px; }
@media (max-width: 960px) {
  .chat-layout { grid-template-columns: 1fr; }
  .chat-sidebar { display: none; }
  .chat-content { padding: 24px 16px 12px; }
}
```

- [ ] **Step 3: Run lint to verify shell wiring**

Run: `npm --prefix frontend run lint`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/components/chat/chat-shell.tsx frontend/app/globals.css
git commit -m "feat: add chat shell layout"
```

### Task 5: Replace the main page with session-aware orchestration

**Files:**
- Modify: `frontend/app/page.tsx:1-420`
- Modify: `frontend/lib/api.ts:162-296`

- [ ] **Step 1: Replace the inline CSS page with imported shell usage**

Rewrite `frontend/app/page.tsx` around the existing logic, keeping `use client`, router auth protection, textarea resizing, unauthorized handling, and session-not-found recovery.

The core state should look like:

```tsx
const [messages, setMessages] = useState<ChatUiMessage[]>([])
const [sessions, setSessions] = useState<SessionListItem[]>([])
const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
const [activeSessionTitle, setActiveSessionTitle] = useState('Cuộc tư vấn pháp lý')
const [input, setInput] = useState('')
const [loading, setLoading] = useState(false)
const [theme, setTheme] = useState<'light' | 'dark'>('light')
```

- [ ] **Step 2: Add session bootstrap logic**

Implement helpers inside `frontend/app/page.tsx`:

```tsx
async function hydrateSessions(preferredSessionId?: string | null) {
  const allSessions = await listSessions()
  const resolvedSessionId = preferredSessionId || getStoredSessionId() || allSessions[0]?.id || null

  setSessions(
    allSessions.map((session) => ({
      id: session.id,
      title: session.title || 'Cuộc tư vấn chưa đặt tên',
      preview: 'Mở để xem nội dung',
      updatedLabel: 'Phiên đã lưu',
    })),
  )

  if (!resolvedSessionId) {
    setActiveSessionId(null)
    setMessages([])
    setActiveSessionTitle('Cuộc tư vấn pháp lý')
    return
  }

  setStoredSessionId(resolvedSessionId)
  setActiveSessionId(resolvedSessionId)
  const activeSession = await getSession(resolvedSessionId)
  const sessionMessages = mapMessageHistory(await getMessages(resolvedSessionId))
  setActiveSessionTitle(activeSession.title || 'Cuộc tư vấn pháp lý')
  setMessages(sessionMessages)
}
```

- [ ] **Step 3: Change “new chat” behavior to create a real new session**

Implement:

```tsx
async function handleCreateSession() {
  const session = await createSession('Cuộc tư vấn mới')
  setStoredSessionId(session.id)
  await hydrateSessions(session.id)
}
```

Do not keep the old local-only `clearChat()` behavior.

- [ ] **Step 4: Add rename, delete, copy, and export handlers**

Add these handlers:

```tsx
async function handleRenameSession(sessionId: string) {
  const nextTitle = window.prompt('Nhập tên mới cho phiên tư vấn')?.trim()
  if (!nextTitle) return
  await renameSession(sessionId, nextTitle)
  await hydrateSessions(sessionId)
}

async function handleDeleteSession(sessionId: string) {
  const confirmed = window.confirm('Xóa phiên tư vấn này?')
  if (!confirmed) return
  await deleteSession(sessionId)
  if (activeSessionId === sessionId) {
    clearStoredSessionId()
  }
  await hydrateSessions(null)
}

async function handleCopy(text: string) {
  await navigator.clipboard.writeText(text)
}

function handleExportSession() {
  const content = buildSessionMarkdown(activeSessionTitle, messages)
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${activeSessionTitle || 'lexvn-session'}.md`
  link.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 5: Render the shell instead of raw markup**

The return should be reduced to:

```tsx
return (
  <ChatShell
    sessions={sessions}
    activeSessionId={activeSessionId}
    activeSessionTitle={activeSessionTitle}
    messages={messages}
    loading={loading}
    input={input}
    userEmail={localStorage.getItem('lexvn-user-email') || 'Tài khoản LexVN'}
    theme={theme}
    textareaRef={textareaRef}
    suggestions={SUGGESTIONS}
    onInputChange={handleInputChange}
    onSubmit={handleFormSubmit}
    onKeyDown={handleKeyDown}
    onAsk={submitMessage}
    onCopy={handleCopy}
    onToggleTheme={toggleTheme}
    onLogout={handleLogout}
    onCreateSession={handleCreateSession}
    onSelectSession={hydrateSessions}
    onRenameSession={handleRenameSession}
    onDeleteSession={handleDeleteSession}
    onExportSession={() => handleExportSession()}
  />
)
```

- [ ] **Step 6: Run lint after the page rewrite**

Run: `npm --prefix frontend run lint`
Expected: PASS

- [ ] **Step 7: Run the frontend locally and verify manual happy path**

Run: `npm --prefix frontend run dev`
Expected: Next.js dev server starts on `http://localhost:3000`

In browser, verify:
- authenticated user lands on redesigned chat page
- welcome state renders before sending first message
- new session creates a separate history item
- selecting a session swaps message history
- rename works
- delete works
- copy button copies assistant content
- export creates a `.md` download

- [ ] **Step 8: Commit**

```bash
git add frontend/app/page.tsx frontend/lib/api.ts
git commit -m "feat: redesign chat workspace"
```

### Task 6: Build auth presentational components

**Files:**
- Create: `frontend/components/auth/auth-shell.tsx`
- Create: `frontend/components/auth/auth-hero.tsx`
- Create: `frontend/components/auth/auth-panel.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Create the auth hero and auth panel components**

Create `frontend/components/auth/auth-hero.tsx`:

```tsx
export function AuthHero() {
  return (
    <section className="auth-hero">
      <div className="auth-hero__eyebrow">Hồ sơ pháp lý riêng tư · Tiếp nối theo phiên</div>
      <h1 className="auth-hero__title">
        Một không gian <em>trang trọng</em> để tiếp tục từng mạch tư vấn pháp lý.
      </h1>
      <p className="auth-hero__copy">
        LexVN kết hợp trải nghiệm số tinh gọn với cảm giác tin cậy của một workspace dành riêng cho nghiên cứu, trao đổi và lưu vết lập luận pháp lý.
      </p>
      <div className="auth-pillars">
        <div className="auth-pillar"><strong>Riêng tư</strong><span>Phiên tư vấn gắn với từng tài khoản.</span></div>
        <div className="auth-pillar"><strong>Liên tục</strong><span>Quay lại đúng hồ sơ đang theo dõi.</span></div>
        <div className="auth-pillar"><strong>Chuẩn mực</strong><span>Ngôn ngữ thiết kế thống nhất với toàn bộ workspace.</span></div>
      </div>
      <blockquote className="auth-quote">“Một hồ sơ tốt không chỉ lưu dữ kiện — nó giữ lại mạch lập luận và lịch sử quyết định.”</blockquote>
    </section>
  )
}
```

Create `frontend/components/auth/auth-panel.tsx` as a prop-driven form component that accepts:
- `mode`
- `email`
- `password`
- `confirmPassword`
- `loading`
- `error`
- `success`
- change callbacks
- submit callback
- mode toggle callback

- [ ] **Step 2: Create the shell component**

Create `frontend/components/auth/auth-shell.tsx`:

```tsx
import { AuthHero } from './auth-hero'
import { AuthPanel } from './auth-panel'

export function AuthShell(props: React.ComponentProps<typeof AuthPanel>) {
  return (
    <div className="auth-layout">
      <AuthHero />
      <div className="auth-panel-wrap">
        <AuthPanel {...props} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add shared auth styles to `frontend/app/globals.css`**

Append:

```css
.auth-layout { min-height: 100vh; display: grid; grid-template-columns: 1.1fr 0.9fr; }
.auth-hero { padding: 48px 56px; border-right: 1px solid var(--color-border); }
.auth-panel-wrap { display: grid; place-items: center; padding: 32px 20px; }
@media (max-width: 980px) {
  .auth-layout { grid-template-columns: 1fr; }
  .auth-hero { border-right: 0; border-bottom: 1px solid var(--color-border); padding: 32px 24px 18px; }
}
```

- [ ] **Step 4: Run lint to verify auth components compile**

Run: `npm --prefix frontend run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/auth frontend/app/globals.css
git commit -m "feat: add auth ui components"
```

### Task 7: Replace the auth page with the new shell while preserving behavior

**Files:**
- Modify: `frontend/app/auth/page.tsx:1-367`

- [ ] **Step 1: Preserve the current state and auth logic**

Keep these state variables and flows:

```tsx
const [mode, setMode] = useState<Mode>('login')
const [theme, setTheme] = useState<Theme>('light')
const [email, setEmail] = useState('')
const [password, setPassword] = useState('')
const [confirmPassword, setConfirmPassword] = useState('')
const [loading, setLoading] = useState(false)
const [error, setError] = useState('')
const [success, setSuccess] = useState('')
```

And preserve the existing validation rules:
- required email/password
- register password length >= 8
- register password confirmation match

- [ ] **Step 2: Replace inline JSX with `AuthShell` usage**

Refactor the page to render:

```tsx
<AuthShell
  mode={mode}
  email={email}
  password={password}
  confirmPassword={confirmPassword}
  loading={loading}
  error={error}
  success={success}
  onModeChange={(nextMode) => {
    setMode(nextMode)
    setError('')
    setSuccess('')
  }}
  onEmailChange={setEmail}
  onPasswordChange={setPassword}
  onConfirmPasswordChange={setConfirmPassword}
  onSubmit={handleSubmit}
/>
```

Keep `toggleTheme()` accessible from the shell or panel header if included there.

- [ ] **Step 3: Run lint after the auth page rewrite**

Run: `npm --prefix frontend run lint`
Expected: PASS

- [ ] **Step 4: Run browser verification for auth flows**

With the frontend dev server running, verify:
- unauthenticated user reaches redesigned auth page
- login works and redirects to `/`
- register validation still blocks short password and mismatch confirmation
- successful auth still stores credentials and redirects correctly
- theme choice remains consistent across `/auth` and `/`

- [ ] **Step 5: Commit**

```bash
git add frontend/app/auth/page.tsx
git commit -m "feat: redesign auth experience"
```

### Task 8: Manual polish and regression pass

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/components/chat/*.tsx`
- Modify: `frontend/components/auth/*.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/auth/page.tsx`

- [ ] **Step 1: Check mobile and desktop responsiveness**

Verify these states in the browser:
- desktop chat with long markdown answer
- mobile chat with sidebar hidden/drawer behavior fallback
- empty chat state
- several sessions in sidebar
- auth page on narrow viewport

- [ ] **Step 2: Tighten typography and spacing only where the UI feels crowded**

Allowed polish changes:
- reduce overly large padding
- widen reading column slightly if markdown wraps too early
- soften chip density for sources
- refine CTA/button sizes

Do not add new features here.

- [ ] **Step 3: Run final lint pass**

Run: `npm --prefix frontend run lint`
Expected: PASS

- [ ] **Step 4: Record final manual verification checklist in the PR notes or handoff**

Checklist:
- [ ] login flow works
- [ ] register flow works
- [ ] restore existing session on refresh works
- [ ] create new session works
- [ ] switch session works
- [ ] rename session works
- [ ] delete session works
- [ ] export Markdown works
- [ ] copy answer works
- [ ] light/dark theme stays in sync across auth and chat
- [ ] mobile layout remains usable

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css frontend/components/chat frontend/components/auth frontend/app/page.tsx frontend/app/auth/page.tsx
git commit -m "style: polish redesigned frontend workspace"
```

## Self-review

### Spec coverage
- Shared visual system: covered in Tasks 1, 4, 6, 8
- Multi-session sidebar and session actions: covered in Tasks 3, 4, 5
- Copy/export/profile UX: covered in Tasks 3 and 5
- Auth redesign: covered in Tasks 6 and 7
- Responsive behavior: covered in Tasks 4, 6, and 8
- Preservation of existing auth/chat behavior: covered in Tasks 5 and 7

### Placeholder scan
- No TODO/TBD placeholders remain
- Each code-writing step names exact files and includes concrete snippets
- Each verification step includes explicit commands or manual checks

### Type consistency
- `ChatUiMessage` is the shared frontend message type throughout the plan
- `SessionListItem` is the shared sidebar item type throughout the plan
- Export helper and shell components use those same names consistently
