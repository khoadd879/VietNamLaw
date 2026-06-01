'use client'

import type { FormEvent, KeyboardEvent, RefObject } from 'react'

interface ChatComposerProps {
  input: string
  loading: boolean
  textareaRef: RefObject<HTMLTextAreaElement>
  onChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}

export function ChatComposer({
  input,
  loading,
  textareaRef,
  onChange,
  onSubmit,
  onKeyDown,
}: ChatComposerProps) {
  const canSend = input.trim().length > 0 && !loading

  return (
    <div className="chat-composer-shell">
      <div className="chat-disclaimer" role="note">
        <span className="chat-disclaimer__icon" aria-hidden="true">ℹ️</span>
        <span>
          Thông tin tư vấn mang tính tham khảo. Vui lòng tham khảo luật sư có thẩm quyền
          cho các vấn đề pháp lý quan trọng.
        </span>
      </div>

      <form onSubmit={onSubmit}>
        <div className="chat-composer">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Hỏi bất kỳ vấn đề pháp lý nào…"
            rows={1}
            aria-label="Nhập câu hỏi"
          />
          <button
            type="submit"
            className="chat-send-btn"
            disabled={!canSend}
            title="Gửi câu hỏi"
            aria-label="Gửi"
          >
            <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </form>

      <div className="chat-composer-hint" aria-hidden="true">
        Nhấn <kbd>Enter</kbd> để gửi &nbsp;·&nbsp; <kbd>Shift+Enter</kbd> để xuống dòng
      </div>
    </div>
  )
}
