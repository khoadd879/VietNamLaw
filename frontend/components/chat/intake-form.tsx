'use client'

import { useState } from 'react'
import { submitIntake, createSession, type IntakeResponse } from '@/lib/api'

const CASE_TYPES = [
  { value: 'hôn nhân gia đình', label: 'Hôn nhân & Gia đình' },
  { value: 'lao động', label: 'Lao động' },
  { value: 'đất đai', label: 'Đất đai & Nhà ở' },
  { value: 'hợp đồng', label: 'Hợp đồng dân sự' },
  { value: 'thừa kế', label: 'Thừa kế' },
  { value: 'hành chính', label: 'Hành chính' },
  { value: 'hình sự', label: 'Hình sự (sẽ chuyển luật sư chuyên môn)' },
  { value: 'khác', label: 'Khác' },
] as const

interface IntakeFormProps {
  sessionId: string | null
  onComplete: (resp: IntakeResponse) => void
  onSessionCreated?: (sessionId: string) => void
}

export function IntakeForm({ sessionId, onComplete, onSessionCreated }: IntakeFormProps) {
  const [caseType, setCaseType] = useState('')
  const [caseSummary, setCaseSummary] = useState('')
  const [facts, setFacts] = useState<Array<{ key: string; value: string }>>([
    { key: '', value: '' },
  ])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const addFactRow = () => setFacts([...facts, { key: '', value: '' }])
  const removeFactRow = (i: number) => setFacts(facts.filter((_, idx) => idx !== i))
  const updateFact = (i: number, field: 'key' | 'value', val: string) => {
    const next = facts.slice()
    next[i] = { ...next[i], [field]: val }
    setFacts(next)
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!caseType) { setError('Vui lòng chọn loại vụ việc'); return }
    if (!caseSummary.trim()) { setError('Vui lòng tóm tắt vụ việc'); return }
    const cleanFacts = facts.filter(f => f.key.trim() && f.value.trim())
    setSubmitting(true)
    try {
      // If parent hasn't created a session yet (first visit), create one now so
      // the intake payload has a real session_id. Without this, /chat/intake
      // returns 422 because session_id is required.
      let activeId = sessionId
      if (!activeId) {
        const session = await createSession('Cuộc tư vấn mới')
        activeId = session.id
        if (typeof window !== 'undefined') {
          window.localStorage.setItem('vnl_active_session_id', activeId)
        }
        onSessionCreated?.(activeId)
      }
      const resp = await submitIntake({
        session_id: activeId,
        case_type: caseType,
        case_summary: caseSummary,
        initial_facts: cleanFacts,
      })
      onComplete(resp)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi không xác định')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="intake-form" onSubmit={onSubmit} aria-labelledby="intake-heading">
      <h2 id="intake-heading">Bắt đầu tư vấn</h2>
      <p className="intake-hint">
        Trước khi tư vấn, luật sư cần biết loại vụ việc và một vài thông tin cơ bản.
        Bạn có thể bổ sung thêm trong quá trình chat.
      </p>

      <label className="intake-label">
        Loại vụ việc
        <select
          value={caseType}
          onChange={(e) => setCaseType(e.target.value)}
          required
        >
          <option value="">-- Chọn loại vụ --</option>
          {CASE_TYPES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </label>

      <label className="intake-label">
        Tóm tắt vụ việc
        <textarea
          value={caseSummary}
          onChange={(e) => setCaseSummary(e.target.value)}
          rows={4}
          placeholder="Ví dụ: Tôi kết hôn năm 2018, hiện muốn ly hôn đơn phương, có 1 con chung 3 tuổi..."
          required
        />
      </label>

      <fieldset className="intake-facts">
        <legend>Facts pháp lý ban đầu (tuỳ chọn)</legend>
        {facts.map((f, i) => (
          <div key={i} className="intake-fact-row">
            <input
              type="text"
              placeholder="key (vd: ngay_ket_hon)"
              value={f.key}
              onChange={(e) => updateFact(i, 'key', e.target.value)}
            />
            <input
              type="text"
              placeholder="giá trị (vd: 2018-03-15)"
              value={f.value}
              onChange={(e) => updateFact(i, 'value', e.target.value)}
            />
            <button type="button" onClick={() => removeFactRow(i)} aria-label="Xoá dòng">
              ✕
            </button>
          </div>
        ))}
        <button type="button" onClick={addFactRow}>+ Thêm fact</button>
      </fieldset>

      {error && <div role="alert" className="intake-error">{error}</div>}

      <button type="submit" disabled={submitting} className="intake-submit">
        {submitting ? 'Đang gửi...' : 'Bắt đầu tư vấn'}
      </button>
    </form>
  )
}