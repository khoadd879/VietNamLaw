'use client'

import type { SuggestionCard } from './chat.types'

interface WelcomeStateProps {
  suggestions: SuggestionCard[]
  onAsk: (question: string) => void
}

export function WelcomeState({ suggestions, onAsk }: WelcomeStateProps) {
  return (
    <section className="chat-welcome">
      <div className="chat-welcome__badge">LexVN · Không gian tư vấn pháp lý</div>

      <h1 className="chat-welcome__title">
        Tư duy pháp lý rõ ràng, trong một <em>workspace</em> trang trọng.
      </h1>

      <p className="chat-welcome__copy">
        Trao đổi, lưu vết lập luận, và tiếp tục từng hồ sơ tư vấn với trải nghiệm
        đọc viết được tối ưu cho nội dung pháp lý.
      </p>

      <div className="chat-welcome__grid">
        {suggestions.map((card) => (
          <button
            key={card.title}
            type="button"
            className="chat-prompt-card"
            onClick={() => onAsk(card.q)}
          >
            <span className="chat-prompt-card__title">{card.title}</span>
            <span className="chat-prompt-card__desc">{card.desc}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
