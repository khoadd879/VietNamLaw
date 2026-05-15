'use client'

import { useState, useRef, useEffect, FormEvent, KeyboardEvent } from 'react'
import { useRouter } from 'next/navigation'
import {
  clearAuthState,
  isLoggedIn,
  isNotFoundError,
  isUnauthorizedError,
  loadSessionHistory,
  resetSession,
  sendAuthedMessage,
} from '@/lib/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

const SUGGESTIONS = [
  { title: '👨‍👩‍👧 Hôn nhân & Gia đình', desc: 'Ly hôn, quyền nuôi con, chia tài sản', q: 'Thủ tục ly hôn đơn phương cần chuẩn bị những gì?' },
  { title: '🏢 Doanh nghiệp', desc: 'Thành lập, giải thể, quản trị công ty', q: 'Công ty TNHH và CTCP khác nhau như thế nào?' },
  { title: '⚡ Lao động', desc: 'Hợp đồng, sa thải, lương thưởng, BHXH', q: 'Người lao động bị sa thải trái luật được bồi thường như thế nào?' },
  { title: '🏠 Đất đai & Nhà ở', desc: 'Sổ đỏ, tranh chấp, chuyển nhượng', q: 'Tranh chấp đất đai với hàng xóm phải làm gì?' },
]

function parseMarkdown(text: string): string {
  let t = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  t = t.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  t = t.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>')

  t = t.replace(/((?:^[-*] .+\n?)+)/gm, (block) => {
    const items = block.trim().split('\n').map(l => `<li>${l.replace(/^[-*] /, '')}</li>`).join('')
    return `<ul>${items}</ul>`
  })
  t = t.replace(/((?:^\d+\. .+\n?)+)/gm, (block) => {
    const items = block.trim().split('\n').map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`).join('')
    return `<ol>${items}</ol>`
  })

  t = t
    .split(/\n{2,}/)
    .map(para => {
      para = para.trim()
      if (!para) return ''
      if (para.match(/^<(h[34]|ul|ol)/)) return para
      return `<p>${para.replace(/\n/g, '<br>')}</p>`
    })
    .join('')

  return t
}

export default function Home() {
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [inputFocused, setInputFocused] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

    loadSessionHistory()
      .then(setMessages)
      .catch((error: unknown) => {
        if (isUnauthorizedError(error)) {
          clearAuthState()
          router.replace('/auth')
          return
        }

        if (isNotFoundError(error)) {
          resetSession().catch(() => undefined)
        }
      })
  }, [router])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function adjustHeight() {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'
  }

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    adjustHeight()
  }

  async function submitMessage(text: string) {
    if (!text.trim() || loading) return

    if (!isLoggedIn()) {
      router.replace('/auth')
      return
    }

    const userMsg: ChatMessage = { role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setLoading(true)

    try {
      const res = await sendAuthedMessage(text.trim())
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.reply, sources: res.sources },
      ])
    } catch (error) {
      if (isUnauthorizedError(error)) {
        clearAuthState()
        router.replace('/auth')
        return
      }

      if (isNotFoundError(error)) {
        try {
          await resetSession()
          const res = await sendAuthedMessage(text.trim())
          setMessages(prev => [
            ...prev,
            { role: 'assistant', content: res.reply, sources: res.sources },
          ])
          return
        } catch {
          setMessages(prev => [
            ...prev,
            { role: 'assistant', content: '⚠️ Không thể khôi phục phiên chat. Vui lòng thử lại.' },
          ])
          return
        }
      }

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: '⚠️ Không thể kết nối. Vui lòng thử lại.' },
      ])
    } finally {
      setLoading(false)
    }
  }

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

  function toggleTheme() {
    const next: 'light' | 'dark' = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('lexvn-theme', next)
  }

  function clearChat() {
    setMessages([])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    resetSession().catch(() => undefined)
  }

  function ask(q: string) {
    submitMessage(q)
  }

  const canSend = input.trim().length > 0 && !loading

  return (
    <>
      <style suppressHydrationWarning>{`
        :root {
          --gold: #B8965A;
          --gold-light: #D4AF6E;
          --gold-pale: #F7F1E6;
          --gold-deep: #8B6E3D;
          --bg: #F6F2EC;
          --surface: #FFFFFF;
          --surface2: #F0EAE0;
          --text: #1C1610;
          --text2: #5A4D3A;
          --text3: #9A8870;
          --border: rgba(184,150,90,0.16);
          --border-md: rgba(184,150,90,0.32);
          --shadow: 0 2px 16px rgba(80,50,10,0.07);
          --shadow-lg: 0 6px 36px rgba(80,50,10,0.12);
          --r: 14px;
          --t: 0.2s cubic-bezier(0.4,0,0.2,1);
        }
        [data-theme="dark"] {
          --bg: #0F0C08;
          --surface: #1A1510;
          --surface2: #231D12;
          --text: #EDE4D4;
          --text2: #C0A878;
          --text3: #6E5E46;
          --border: rgba(184,150,90,0.12);
          --border-md: rgba(184,150,90,0.26);
          --shadow: 0 2px 16px rgba(0,0,0,0.35);
          --shadow-lg: 0 6px 36px rgba(0,0,0,0.50);
          --gold-pale: #231A0C;
        }
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html { height: 100%; overflow: hidden; }
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; transition: background var(--t), color var(--t); }
        header { flex-shrink: 0; height: 58px; background: var(--surface); border-bottom: 1px solid var(--border); box-shadow: var(--shadow); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; z-index: 10; }
        .brand { display: flex; align-items: center; gap: 10px; }
        .brand-logo { width: 36px; height: 36px; background: linear-gradient(140deg, var(--gold) 0%, var(--gold-deep) 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-family: 'Cormorant Garamond', serif; font-size: 17px; font-weight: 600; color: #fff; }
        .brand-text { display: flex; flex-direction: column; line-height: 1.15; }
        .brand-name { font-family: 'Cormorant Garamond', serif; font-size: 19px; font-weight: 600; color: var(--gold); }
        .brand-tagline { font-size: 10px; color: var(--text3); letter-spacing: 1.8px; text-transform: uppercase; }
        .header-center { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text3); font-weight: 500; }
        .dot-live { width: 6px; height: 6px; border-radius: 50%; background: #2ECC71; animation: blink 2.4s infinite; }
        @keyframes blink { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.3)} }
        .header-actions { display: flex; gap: 7px; }
        .hbtn { width: 34px; height: 34px; border-radius: 9px; background: transparent; border: 1px solid var(--border); color: var(--text2); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all var(--t); }
        .hbtn:hover { background: var(--gold-pale); color: var(--gold); border-color: var(--border-md); }
        [data-theme="dark"] .sun { display: none; }
        [data-theme="light"] .moon { display: none; }
        .chat-wrap { flex: 1; overflow: hidden; display: flex; flex-direction: column; max-width: 820px; width: 100%; margin: 0 auto; padding: 0 16px; }
        .messages { flex: 1; overflow-y: auto; padding: 28px 0 12px; display: flex; flex-direction: column; gap: 20px; scrollbar-width: thin; scrollbar-color: var(--border-md) transparent; }
        .messages::-webkit-scrollbar { width: 4px; }
        .messages::-webkit-scrollbar-thumb { background: var(--border-md); border-radius: 99px; }
        .welcome { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 36px 16px 20px; gap: 20px; animation: fadeUp .4s ease-out; }
        .welcome-avatar { width: 68px; height: 68px; background: linear-gradient(140deg, var(--gold) 0%, var(--gold-deep) 100%); border-radius: 20px; display: flex; align-items: center; justify-content: center; font-family: 'Cormorant Garamond', serif; font-size: 30px; font-weight: 600; color: #fff; box-shadow: 0 6px 24px rgba(184,150,90,0.3); animation: float 4s ease-in-out infinite; }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        .welcome h1 { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-weight: 600; color: var(--text); line-height: 1.3; }
        .welcome h1 em { color: var(--gold); font-style: normal; }
        .welcome p { font-size: 14px; color: var(--text2); line-height: 1.65; max-width: 500px; }
        .suggestions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 9px; width: 100%; max-width: 560px; }
        .sug-btn { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 12px 14px; text-align: left; cursor: pointer; transition: all var(--t); display: flex; flex-direction: column; gap: 4px; }
        .sug-btn:hover { border-color: var(--gold); background: var(--gold-pale); transform: translateY(-2px); box-shadow: var(--shadow); }
        .sug-title { font-size: 13px; font-weight: 600; color: var(--text); line-height: 1.3; }
        .sug-desc { font-size: 11.5px; color: var(--text3); line-height: 1.4; }
        .msg { display: flex; gap: 11px; animation: fadeUp .25s ease-out; }
        .msg.user { flex-direction: row-reverse; }
        @keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        .msg-avatar { width: 32px; height: 32px; border-radius: 9px; flex-shrink: 0; margin-top: 3px; display: flex; align-items: center; justify-content: center; }
        .msg-avatar.bot { background: linear-gradient(140deg, var(--gold), var(--gold-deep)); color: #fff; font-family: 'Cormorant Garamond', serif; font-size: 15px; font-weight: 600; }
        .msg-avatar.user { background: var(--surface2); border: 1px solid var(--border); color: var(--text2); }
        .bubble { max-width: 72%; padding: 12px 16px; border-radius: var(--r); line-height: 1.65; font-size: 14px; }
        .bubble.bot { background: var(--surface); border: 1px solid var(--border); color: var(--text); border-bottom-left-radius: 4px; box-shadow: var(--shadow); }
        .bubble.user { background: linear-gradient(140deg, var(--gold), var(--gold-deep)); color: #fff; border-bottom-right-radius: 4px; box-shadow: 0 3px 12px rgba(184,150,90,0.28); }
        .bubble p { margin-bottom: 8px; }
        .bubble p:last-child { margin-bottom: 0; }
        .bubble strong { font-weight: 600; color: var(--gold-deep); }
        [data-theme="dark"] .bubble strong { color: var(--gold-light); }
        .bubble.user strong { color: rgba(255,255,255,.92); }
        .bubble ul, .bubble ol { margin: 5px 0 8px 18px; display: flex; flex-direction: column; gap: 3px; }
        .bubble li { line-height: 1.6; }
        .bubble code { background: var(--surface2); border-radius: 4px; padding: 1px 5px; font-size: 12.5px; font-family: monospace; }
        .bubble h3, .bubble h4 { font-weight: 600; color: var(--gold-deep); margin-bottom: 5px; font-size: 14px; }
        [data-theme="dark"] .bubble h3, [data-theme="dark"] .bubble h4 { color: var(--gold-light); }
        .bubble-sources { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 11.5px; color: var(--text3); }
        .typing-wrap { display: flex; gap: 11px; animation: fadeUp .25s ease-out; }
        .typing-dots { display: flex; align-items: center; gap: 4px; padding: 14px 16px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); border-bottom-left-radius: 4px; box-shadow: var(--shadow); }
        .td { width: 6px; height: 6px; background: var(--gold); border-radius: 50%; animation: tdB 1.3s infinite ease-in-out; }
        .td:nth-child(2){animation-delay:.15s} .td:nth-child(3){animation-delay:.3s}
        @keyframes tdB { 0%,60%,100%{transform:translateY(0);opacity:.5} 30%{transform:translateY(-7px);opacity:1} }
        .input-section { flex-shrink: 0; padding: 10px 0 18px; }
        .disclaimer { display: flex; align-items: flex-start; gap: 8px; background: rgba(192,57,43,0.05); border: 1px solid rgba(192,57,43,0.12); border-radius: 9px; padding: 8px 12px; margin-bottom: 10px; font-size: 11.5px; color: var(--text2); line-height: 1.5; }
        .disc-icon { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
        .input-box { display: flex; align-items: flex-end; gap: 9px; background: var(--surface); border: 1.5px solid var(--border-md); border-radius: 16px; padding: 10px 10px 10px 16px; box-shadow: var(--shadow-lg); transition: border-color var(--t), box-shadow var(--t); }
        .input-box:focus-within { border-color: var(--gold); box-shadow: 0 4px 20px rgba(184,150,90,0.16), 0 0 0 3px rgba(184,150,90,0.09); }
        #chatInput { flex: 1; border: none; outline: none; background: transparent; font-family: 'DM Sans', sans-serif; font-size: 14px; color: var(--text); line-height: 1.55; resize: none; min-height: 22px; max-height: 150px; scrollbar-width: thin; }
        #chatInput::placeholder { color: var(--text3); }
        .send-btn { width: 38px; height: 38px; border-radius: 11px; background: linear-gradient(140deg, var(--gold), var(--gold-deep)); border: none; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all var(--t); flex-shrink: 0; }
        .send-btn:hover { transform: scale(1.06); box-shadow: 0 4px 14px rgba(184,150,90,0.36); }
        .send-btn:active { transform: scale(.97); }
        .send-btn:disabled { opacity: .38; cursor: not-allowed; transform: none; box-shadow: none; }
        .input-hint { text-align: center; margin-top: 7px; font-size: 10.5px; color: var(--text3); display: flex; align-items: center; justify-content: center; gap: 4px; }
        .input-hint kbd { background: var(--surface2); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-family: inherit; font-size: 10px; }
        .err-bubble { background: rgba(192,57,43,.08); border: 1px solid rgba(192,57,43,.2); color: #922B21; border-radius: var(--r); border-bottom-left-radius: 4px; padding: 12px 16px; font-size: 13.5px; max-width: 72%; }
        [data-theme="dark"] .err-bubble { background: rgba(192,57,43,.12); color: #E8857A; }
      `}</style>

      <header>
        <div className="brand">
          <div className="brand-logo">Lx</div>
          <div className="brand-text">
            <span className="brand-name">LexVN</span>
            <span className="brand-tagline">Luật sư AI · Việt Nam</span>
          </div>
        </div>

        <div className="header-center">
          <div className="dot-live" />
          Đang hoạt động · Phản hồi tức thì
        </div>

        <div className="header-actions">
          <button className="hbtn" onClick={clearChat} title="Cuộc hội thoại mới">
            <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <button className="hbtn" onClick={toggleTheme} title="Đổi giao diện">
            <svg className="sun" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
            <svg className="moon" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          </button>
        </div>
      </header>

      <div className="chat-wrap">
        <div className="messages">
          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-avatar">Lx</div>
              <h1>Xin chào! Tôi là <em>LexVN</em><br />Luật sư AI của bạn</h1>
              <p>
                Tôi am hiểu toàn bộ hệ thống pháp luật Việt Nam — dân sự, hình sự, đất đai,
                lao động, doanh nghiệp, hôn nhân và hơn thế nữa. Hãy hỏi tôi bất kỳ điều gì!
              </p>
              <div className="suggestions">
                {SUGGESTIONS.map(s => (
                  <button key={s.title} className="sug-btn" onClick={() => ask(s.q)}>
                    <div className="sug-title">{s.title}</div>
                    <div className="sug-desc">{s.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`msg ${msg.role}`}>
              <div className={`msg-avatar ${msg.role}`}>
                {msg.role === 'assistant' ? (
                  'Lx'
                ) : (
                  <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                )}
              </div>
              <div className={`bubble ${msg.role}`}>
                {msg.role === 'assistant' ? (
                  <>
                    <div dangerouslySetInnerHTML={{ __html: parseMarkdown(msg.content) }} />
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="bubble-sources">📚 Nguồn: {msg.sources.join(', ')}</div>
                    )}
                  </>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="typing-wrap">
              <div className="msg-avatar bot">Lx</div>
              <div className="typing-dots">
                <div className="td" />
                <div className="td" />
                <div className="td" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-section">
          <div className="disclaimer">
            <span className="disc-icon">ℹ️</span>
            <span>Thông tin tư vấn mang tính tham khảo. Vui lòng tham khảo luật sư có thẩm quyền cho các vấn đề pháp lý quan trọng.</span>
          </div>
          <form onSubmit={handleFormSubmit}>
            <div className={`input-box${inputFocused ? ' focused' : ''}`}>
              <textarea
                id="chatInput"
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                placeholder="Hỏi bất kỳ vấn đề pháp lý nào…"
                rows={1}
              />
              <button type="submit" className="send-btn" disabled={!canSend} title="Gửi">
                <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </form>
          <div className="input-hint">
            Nhấn <kbd>Enter</kbd> để gửi &nbsp;·&nbsp; <kbd>Shift+Enter</kbd> để xuống dòng
          </div>
        </div>
      </div>
    </>
  )
}