export function AuthHero() {
  return (
    <section className="auth-hero">
      {/* Topbar with brand and theme toggle */}
      <div className="auth-topbar">
        <div className="auth-brand">
          <div className="auth-brand-logo">Lx</div>
          <div>
            <div className="auth-brand-name">LexVN</div>
            <div className="auth-brand-tag">Luật sư AI · Việt Nam</div>
          </div>
        </div>
      </div>

      {/* Hero body */}
      <div className="auth-hero-body">
        <div className="auth-eyebrow">
          <span className="auth-live-dot" aria-hidden="true" />
          Hồ sơ pháp lý riêng tư · Lưu theo phiên làm việc
        </div>

        <h1>
          Không gian <em>pháp lý cá nhân</em> cho mỗi thân chủ.
        </h1>

        <p className="auth-hero-copy">
          LexVN kết hợp vẻ chuẩn mực của phòng tư vấn luật hiện đại với trải nghiệm số tinh gọn.
          Đăng nhập để truy cập lịch sử trao đổi, lưu theo phiên tư vấn và tiếp tục các hồ sơ đang theo dõi.
        </p>

        <div className="stat-grid">
          <div className="stat">
            <strong>Riêng tư</strong>
            <span>Phiên chat gắn với tài khoản, tách biệt theo người dùng.</span>
          </div>
          <div className="stat">
            <strong>Liên tục</strong>
            <span>Quay lại đúng mạch trao đổi pháp lý đang thực hiện.</span>
          </div>
          <div className="stat">
            <strong>Chuẩn mực</strong>
            <span>Thiết kế đồng bộ với ngôn ngữ thương hiệu LexVN.</span>
          </div>
        </div>

        <blockquote className="auth-quote">
          “Một hồ sơ tốt không chỉ lưu dữ kiện — nó giữ lại mạch lập luận,
          ngữ cảnh vụ việc và lịch sử quyết định.”
        </blockquote>
      </div>
    </section>
  )
}
