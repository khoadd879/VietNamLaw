'use client'

import { useState } from 'react'

interface LegalCitationChipProps {
  citation: string
  sourceUrl?: string
}

const ARTICLE_RE = /(Điều\s+\d+[^,;\n]*?)(?=,|$|;|\n|Khoản|Điểm)/i
const KHOAN_RE = /Khoản\s+\d+/i
const DIEM_RE = /Điểm\s+[a-z]\d*/i

export function parseCitation(citation: string): { article?: string; khoan?: string; diem?: string; raw: string } {
  const articleMatch = citation.match(ARTICLE_RE)
  const khoanMatch = citation.match(KHOAN_RE)
  const diemMatch = citation.match(DIEM_RE)
  return {
    article: articleMatch?.[1]?.trim(),
    khoan: khoanMatch?.[0]?.trim(),
    diem: diemMatch?.[0]?.trim(),
    raw: citation,
  }
}

export function LegalCitationChip({ citation, sourceUrl }: LegalCitationChipProps) {
  const [expanded, setExpanded] = useState(false)
  const parsed = parseCitation(citation)
  const label = [parsed.diem, parsed.khoan, parsed.article].filter(Boolean).join(' · ') || citation

  return (
    <span className="legal-citation-chip" role="button" tabIndex={0}
      onClick={() => setExpanded((v) => !v)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded((v) => !v) }}
      aria-expanded={expanded}
      aria-label={`Trích dẫn: ${citation}`}
    >
      <span className="legal-citation-label">📜 {label}</span>
      {expanded && (
        <span className="legal-citation-detail" role="tooltip">
          {sourceUrl ? (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
              Mở văn bản gốc ↗
            </a>
          ) : (
            <em>Không có link nguồn</em>
          )}
        </span>
      )}
    </span>
  )
}