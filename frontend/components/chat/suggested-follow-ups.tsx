'use client'

interface SuggestedFollowUpsProps {
  questions: string[]
  onSelect: (question: string) => void
}

export function SuggestedFollowUps({ questions, onSelect }: SuggestedFollowUpsProps) {
  if (!questions.length) return null
  return (
    <div className="suggested-follow-ups" aria-label="Câu hỏi gợi ý tiếp theo">
      <p className="follow-ups-label">Có thể bạn muốn hỏi tiếp:</p>
      <ul>
        {questions.map((q, i) => (
          <li key={i}>
            <button type="button" className="follow-up-chip" onClick={() => onSelect(q)}>
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}