'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { LawyerSection } from '@/lib/api'

interface LawyerResponseViewProps {
  section: LawyerSection
  sources: string[] | undefined
}

export function LawyerResponseView({ section, sources }: LawyerResponseViewProps) {
  const hasAny =
    section.loi_chao ||
    section.tom_tat_vu_viec ||
    section.phan_tich_phap_ly ||
    section.phuong_an_khuyen_nghi.length > 0 ||
    section.rui_ro_can_luu_y.length > 0 ||
    section.cau_hoi_hoi_them.length > 0

  if (!hasAny) {
    // Defensive: backend forgot to populate, fall back to plain text
    return null
  }

  return (
    <div className="lawyer-response" data-testid="lawyer-response">
      {section.loi_chao && (
        <p className="lawyer-greeting" role="doc-subtitle">
          {section.loi_chao}
        </p>
      )}

      {section.tom_tat_vu_viec && (
        <section aria-label="Tóm tắt vụ việc">
          <h4>Tóm tắt vụ việc</h4>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.tom_tat_vu_viec}</ReactMarkdown>
        </section>
      )}

      {section.phan_tich_phap_ly && (
        <section aria-label="Phân tích pháp lý">
          <h4>Phân tích pháp lý</h4>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.phan_tich_phap_ly}</ReactMarkdown>
        </section>
      )}

      {section.phuong_an_khuyen_nghi.length > 0 && (
        <section aria-label="Phương án khuyến nghị">
          <h4>Phương án khuyến nghị</h4>
          <ul>
            {section.phuong_an_khuyen_nghi.map((p, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{p}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.rui_ro_can_luu_y.length > 0 && (
        <section aria-label="Rủi ro cần lưu ý" className="lawyer-warn-block">
          <h4>⚠️ Rủi ro cần lưu ý</h4>
          <ul>
            {section.rui_ro_can_luu_y.map((r, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{r}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.cau_hoi_hoi_them.length > 0 && (
        <section aria-label="Câu hỏi cần bạn cung cấp thêm" className="lawyer-ask-block">
          <h4>📋 Câu hỏi cần bạn cung cấp thêm</h4>
          <ul>
            {section.cau_hoi_hoi_them.map((c, i) => (
              <li key={i}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{c}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </section>
      )}

      {section.disclaimer && (
        <aside className="lawyer-disclaimer" role="note">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.disclaimer}</ReactMarkdown>
        </aside>
      )}

      {/*
        Only render the sources block when the LLM actually cited something.
        `sources` from the API are just the raw URLs of retrieved chunks and
        are only meaningful when paired with a real citation; otherwise they
        look authoritative but tell the user nothing.
      */}
      {section.trich_dan_nguon.length > 0 ? (
        <div className="message-sources" aria-label="Nguồn tham khảo">
          {section.trich_dan_nguon.map((cite, i) => (
            <span key={`${cite}-${i}`} className="message-source-chip">
              {cite}
              {sources?.[i] && (
                <a
                  href={sources[i]}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="message-source-link"
                  aria-label={`Mở nguồn: ${cite}`}
                >
                  ↗
                </a>
              )}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
