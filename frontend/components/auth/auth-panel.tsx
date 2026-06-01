'use client'

import Link from 'next/link'
import type { FormEvent } from 'react'

type Mode = 'login' | 'register'
type Theme = 'light' | 'dark'

export interface AuthPanelProps {
  mode: Mode
  email: string
  password: string
  confirmPassword: string
  loading: boolean
  error: string
  success: string
  theme: Theme
  onModeChange: (mode: Mode) => void
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onConfirmPasswordChange: (value: string) => void
  onSubmit: (e: FormEvent) => void
  onToggleTheme: () => void
}

const TITLE: Record<Mode, string> = {
  login: 'Đăng nhập tài khoản',
  register: 'Tạo hồ sơ pháp lý riêng',
}

const SUBTITLE: Record<Mode, string> = {
  login:
    'Truy cập lịch sử tư vấn, phiên làm việc và không gian pháp lý cá nhân của bạn.',
  register:
    'Đăng ký để lưu hội thoại theo hồ sơ cá nhân và bắt đầu hành trình tư vấn cùng LexVN.',
}

export function AuthPanel({
  mode,
  email,
  password,
  confirmPassword,
  loading,
  error,
  success,
  theme,
  onModeChange,
  onEmailChange,
  onPasswordChange,
  onConfirmPasswordChange,
  onSubmit,
  onToggleTheme,
}: AuthPanelProps) {
  return (
    <section className="auth-panel-wrap">
      <div className="auth-panel">
        {/* Theme toggle, top-right */}
        <div style={{ textAlign: 'right', marginBottom: '16px' }}>
          <button
            type="button"
            className="auth-theme-btn"
            onClick={onToggleTheme}
            aria-label="Đổi giao diện sáng/tối"
          >
            <svg className="icon-sun" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
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
            <svg className="icon-moon" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          </button>
        </div>

        {/* Mode tabs */}
        <div className="auth-tabs">
          <button
            type="button"
            className={`auth-tab${mode === 'login' ? ' active' : ''}`}
            onClick={() => onModeChange('login')}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            className={`auth-tab${mode === 'register' ? ' active' : ''}`}
            onClick={() => onModeChange('register')}
          >
            Đăng ký
          </button>
        </div>

        <h2 className="auth-panel-title">{TITLE[mode]}</h2>
        <p className="auth-panel-subtitle">{SUBTITLE[mode]}</p>

        <form onSubmit={onSubmit}>
          <div className="auth-field">
            <label className="auth-label" htmlFor="auth-email">Email</label>
            <input
              id="auth-email"
              className="auth-input"
              type="email"
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              placeholder="ten@vanphongluat.vn"
              autoComplete="email"
              required
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="auth-password">Mật khẩu</label>
            <input
              id="auth-password"
              className="auth-input"
              type="password"
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              placeholder="Tối thiểu 8 ký tự"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
            />
          </div>

          {mode === 'register' && (
            <div className="auth-field">
              <label className="auth-label" htmlFor="auth-confirm">Xác nhận mật khẩu</label>
              <input
                id="auth-confirm"
                className="auth-input"
                type="password"
                value={confirmPassword}
                onChange={(e) => onConfirmPasswordChange(e.target.value)}
                placeholder="Nhập lại mật khẩu"
                autoComplete="new-password"
                required
              />
            </div>
          )}

          <button
            type="submit"
            className="auth-submit"
            disabled={loading}
          >
            {loading
              ? 'Đang xử lý…'
              : mode === 'login'
                ? 'Tiếp tục vào hệ thống'
                : 'Tạo tài khoản LexVN'}
          </button>
        </form>

        {error && (
          <div className="auth-feedback error" role="alert">
            {error}
          </div>
        )}
        {success && (
          <div className="auth-feedback success" role="status">
            {success}
          </div>
        )}

        <div className="auth-footnote">
          Bằng việc tiếp tục, bạn đồng ý lưu phiên tư vấn theo tài khoản
          để phục vụ lịch sử trao đổi và quản lý hồ sơ pháp lý cá nhân.
        </div>

        <Link className="auth-return-link" href="/">
          <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M19 12H5" />
            <path d="m12 19-7-7 7-7" />
          </svg>
          Quay lại giao diện chat
        </Link>
      </div>
    </section>
  )
}
