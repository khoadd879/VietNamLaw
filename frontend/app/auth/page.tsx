'use client'

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { login, register, storeAuthState } from '@/lib/api'

type Mode = 'login' | 'register'
type Theme = 'light' | 'dark'

export default function AuthPage() {
  const router = useRouter()
  const [mode, setMode] = useState<Mode>('login')
  const [theme, setTheme] = useState<Theme>('light')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    const saved = localStorage.getItem('lexvn-theme') as Theme | null
    const next = saved || 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
  }, [])

  function toggleTheme() {
    const next: Theme = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('lexvn-theme', next)
  }

  const title = useMemo(
    () => (mode === 'login' ? 'Đăng nhập tài khoản' : 'Tạo hồ sơ pháp lý riêng'),
    [mode],
  )

  const subtitle = useMemo(
    () =>
      mode === 'login'
        ? 'Truy cập lịch sử tư vấn, phiên làm việc và không gian pháp lý cá nhân của bạn.'
        : 'Đăng ký để lưu hội thoại theo hồ sơ cá nhân và bắt đầu hành trình tư vấn cùng LexVN.',
    [mode],
  )

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (loading) return

    setError('')
    setSuccess('')

    if (!email.trim() || !password.trim()) {
      setError('Vui lòng nhập đầy đủ email và mật khẩu.')
      return
    }

    if (mode === 'register' && password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.')
      return
    }

    setLoading(true)
    try {
      const auth =
        mode === 'login'
          ? await login(email.trim(), password)
          : await register(email.trim(), password)

      storeAuthState(auth)

      setSuccess(
        mode === 'login'
          ? 'Đăng nhập thành công. Đang chuyển tới trang chat.'
          : 'Đăng ký thành công. Đang chuyển tới trang chat.',
      )
      router.push('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể xử lý yêu cầu.')
    } finally {
      setLoading(false)
    }
  }

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
          --shadow-lg: 0 10px 44px rgba(80,50,10,0.14);
          --r: 18px;
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
          --shadow-lg: 0 14px 52px rgba(0,0,0,0.45);
          --gold-pale: #231A0C;
        }
        * { box-sizing: border-box; }
        body { margin: 0; font-family: 'DM Sans', sans-serif; background: radial-gradient(circle at top, rgba(184,150,90,.12), transparent 28%), var(--bg); color: var(--text); }
        .shell { min-height: 100vh; display: grid; grid-template-columns: 1.1fr 0.9fr; }
        .hero {
          position: relative;
          padding: 48px 56px;
          border-right: 1px solid var(--border);
          background:
            linear-gradient(140deg, rgba(184,150,90,.08), transparent 35%),
            linear-gradient(180deg, rgba(255,255,255,.22), transparent 40%),
            var(--bg);
          overflow: hidden;
        }
        .hero::before {
          content: '';
          position: absolute;
          inset: 28px;
          border: 1px solid var(--border);
          border-radius: 28px;
          pointer-events: none;
        }
        .topbar { display: flex; align-items: center; justify-content: space-between; position: relative; z-index: 1; }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-logo { width: 42px; height: 42px; border-radius: 12px; background: linear-gradient(140deg, var(--gold) 0%, var(--gold-deep) 100%); color: #fff; display: grid; place-items: center; font: 600 19px 'Cormorant Garamond', serif; box-shadow: 0 8px 22px rgba(184,150,90,.28); }
        .brand-name { font: 600 23px 'Cormorant Garamond', serif; color: var(--gold); }
        .brand-tag { font-size: 10px; letter-spacing: 1.8px; text-transform: uppercase; color: var(--text3); }
        .hbtn { width: 38px; height: 38px; border-radius: 11px; background: transparent; border: 1px solid var(--border); color: var(--text2); cursor: pointer; display: grid; place-items: center; transition: all var(--t); }
        .hbtn:hover { background: var(--gold-pale); color: var(--gold); border-color: var(--border-md); }
        [data-theme="dark"] .sun { display: none; }
        [data-theme="light"] .moon { display: none; }
        .hero-body { position: relative; z-index: 1; max-width: 560px; padding-top: 72px; }
        .eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,.45); color: var(--text2); font-size: 12px; backdrop-filter: blur(12px); }
        .live { width: 7px; height: 7px; border-radius: 50%; background: #2ECC71; box-shadow: 0 0 0 6px rgba(46,204,113,.1); }
        .hero h1 { margin: 24px 0 16px; font: 600 56px/1.08 'Cormorant Garamond', serif; letter-spacing: -.02em; }
        .hero h1 em { color: var(--gold); font-style: normal; }
        .hero p { margin: 0 0 28px; color: var(--text2); line-height: 1.78; font-size: 15px; max-width: 510px; }
        .stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
        .stat { padding: 16px; border-radius: 16px; background: rgba(255,255,255,.58); border: 1px solid var(--border); box-shadow: var(--shadow); backdrop-filter: blur(12px); }
        .stat strong { display: block; font: 600 22px 'Cormorant Garamond', serif; color: var(--gold-deep); margin-bottom: 4px; }
        .stat span { font-size: 12px; color: var(--text3); line-height: 1.5; }
        .quote {
          margin-top: 26px;
          padding: 18px 18px 18px 20px;
          border-left: 3px solid var(--gold);
          background: linear-gradient(90deg, rgba(184,150,90,.11), transparent 85%);
          border-radius: 0 16px 16px 0;
          color: var(--text2);
          line-height: 1.8;
        }
        .panel-wrap { display: grid; place-items: center; padding: 34px; }
        .panel {
          width: min(100%, 460px);
          padding: 28px;
          border-radius: 28px;
          background: linear-gradient(180deg, rgba(255,255,255,.9), rgba(255,255,255,.82));
          border: 1px solid var(--border);
          box-shadow: var(--shadow-lg);
          backdrop-filter: blur(18px);
        }
        [data-theme="dark"] .panel { background: linear-gradient(180deg, rgba(26,21,16,.96), rgba(26,21,16,.9)); }
        .tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 22px; padding: 6px; background: var(--surface2); border-radius: 16px; border: 1px solid var(--border); }
        .tab { border: 0; border-radius: 12px; padding: 11px 12px; background: transparent; color: var(--text2); cursor: pointer; font: 600 13px 'DM Sans', sans-serif; transition: all var(--t); }
        .tab.active { background: linear-gradient(140deg, var(--gold), var(--gold-deep)); color: #fff; box-shadow: 0 6px 18px rgba(184,150,90,.24); }
        .panel h2 { margin: 0 0 8px; font: 600 34px/1.15 'Cormorant Garamond', serif; color: var(--text); }
        .panel p { margin: 0 0 22px; color: var(--text2); line-height: 1.7; font-size: 14px; }
        .field { margin-bottom: 14px; }
        .label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--text3); }
        .input {
          width: 100%;
          height: 50px;
          border-radius: 15px;
          border: 1.5px solid var(--border-md);
          background: var(--surface);
          color: var(--text);
          padding: 0 16px;
          outline: none;
          transition: border-color var(--t), box-shadow var(--t), transform var(--t);
          font: 500 14px 'DM Sans', sans-serif;
        }
        .input:focus { border-color: var(--gold); box-shadow: 0 0 0 4px rgba(184,150,90,.09); }
        .submit {
          width: 100%;
          height: 52px;
          border: 0;
          border-radius: 16px;
          margin-top: 8px;
          background: linear-gradient(140deg, var(--gold), var(--gold-deep));
          color: #fff;
          font: 600 14px 'DM Sans', sans-serif;
          cursor: pointer;
          transition: transform var(--t), box-shadow var(--t), opacity var(--t);
          box-shadow: 0 10px 24px rgba(184,150,90,.24);
        }
        .submit:hover { transform: translateY(-1px); box-shadow: 0 14px 28px rgba(184,150,90,.32); }
        .submit:disabled { opacity: .45; cursor: not-allowed; transform: none; box-shadow: none; }
        .feedback { margin-top: 14px; border-radius: 14px; padding: 12px 14px; font-size: 13px; line-height: 1.6; }
        .feedback.error { background: rgba(192,57,43,.08); border: 1px solid rgba(192,57,43,.18); color: #922B21; }
        .feedback.success { background: rgba(46,204,113,.08); border: 1px solid rgba(46,204,113,.18); color: #20744A; }
        .footnote { margin-top: 18px; color: var(--text3); font-size: 11.5px; line-height: 1.65; text-align: center; }
        .return-link { margin-top: 20px; display: inline-flex; align-items: center; gap: 8px; color: var(--gold-deep); text-decoration: none; font-size: 13px; font-weight: 600; }
        .return-link:hover { color: var(--gold); }
        @media (max-width: 980px) {
          .shell { grid-template-columns: 1fr; }
          .hero { padding: 32px 24px 18px; border-right: 0; border-bottom: 1px solid var(--border); }
          .hero::before { inset: 18px; }
          .hero-body { padding-top: 38px; }
          .hero h1 { font-size: 42px; }
          .panel-wrap { padding: 22px 16px 36px; }
        }
        @media (max-width: 640px) {
          .topbar { gap: 12px; }
          .hero h1 { font-size: 36px; }
          .stat-grid { grid-template-columns: 1fr; }
          .panel { padding: 22px 18px; border-radius: 22px; }
        }
      `}</style>

      <div className="shell">
        <section className="hero">
          <div className="topbar">
            <div className="brand">
              <div className="brand-logo">Lx</div>
              <div>
                <div className="brand-name">LexVN</div>
                <div className="brand-tag">Luật sư AI · Việt Nam</div>
              </div>
            </div>

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

          <div className="hero-body">
            <div className="eyebrow">
              <span className="live" />
              Hồ sơ pháp lý riêng tư · Lưu theo phiên làm việc
            </div>
            <h1>
              Không gian <em>pháp lý cá nhân</em> cho mỗi thân chủ.
            </h1>
            <p>
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

            <div className="quote">
              “Một hồ sơ tốt không chỉ lưu dữ kiện — nó giữ lại mạch lập luận, ngữ cảnh vụ việc và lịch sử quyết định.”
            </div>
          </div>
        </section>

        <section className="panel-wrap">
          <div className="panel">
            <div className="tabs">
              <button className={`tab ${mode === 'login' ? 'active' : ''}`} onClick={() => { setMode('login'); setError(''); setSuccess('') }}>
                Đăng nhập
              </button>
              <button className={`tab ${mode === 'register' ? 'active' : ''}`} onClick={() => { setMode('register'); setError(''); setSuccess('') }}>
                Đăng ký
              </button>
            </div>

            <h2>{title}</h2>
            <p>{subtitle}</p>

            <form onSubmit={handleSubmit}>
              <div className="field">
                <label className="label" htmlFor="email">Email</label>
                <input id="email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ten@vanphongluat.vn" autoComplete="email" />
              </div>

              <div className="field">
                <label className="label" htmlFor="password">Mật khẩu</label>
                <input id="password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Tối thiểu 8 ký tự" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
              </div>

              {mode === 'register' && (
                <div className="field">
                  <label className="label" htmlFor="confirmPassword">Xác nhận mật khẩu</label>
                  <input id="confirmPassword" className="input" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Nhập lại mật khẩu" autoComplete="new-password" />
                </div>
              )}

              <button className="submit" type="submit" disabled={loading}>
                {loading ? 'Đang xử lý...' : mode === 'login' ? 'Tiếp tục vào hệ thống' : 'Tạo tài khoản LexVN'}
              </button>
            </form>

            {error && <div className="feedback error">{error}</div>}
            {success && <div className="feedback success">{success}</div>}

            <div className="footnote">
              Bằng việc tiếp tục, bạn đồng ý lưu phiên tư vấn theo tài khoản để phục vụ lịch sử trao đổi và quản lý hồ sơ pháp lý cá nhân.
            </div>

            <a className="return-link" href="/">
              <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M19 12H5" />
                <path d="m12 19-7-7 7-7" />
              </svg>
              Quay lại giao diện chat
            </a>
          </div>
        </section>
      </div>
    </>
  )
}
