'use client'

import { useState } from 'react'

export function DisclaimerBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return (
    <aside className="disclaimer-banner" role="alert">
      <p>
        ⚠️ <strong>Lưu ý:</strong> Nội dung tư vấn mang tính tham khảo, dựa trên cơ sở dữ liệu
        văn bản pháp luật hiện có. Không thay thế ý kiến luật sư hành nghề cho hồ sơ cụ thể
        của bạn. Vụ việc phức tạp nên liên hệ Luật sư đoàn tại địa phương.
      </p>
      <button type="button" onClick={() => setDismissed(true)} aria-label="Đóng cảnh báo">
        ✕
      </button>
    </aside>
  )
}