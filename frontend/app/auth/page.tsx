'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { isLoggedIn, login, register, storeAuthState } from '@/lib/api'
import { AuthHero } from '@/components/auth/auth-hero'
import { AuthPanel } from '@/components/auth/auth-panel'

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

  // ── Bootstrap ────────────────────────────────────────────
  useEffect(() => {
    const saved = localStorage.getItem('lexvn-theme') as Theme | null
    const next = saved || 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)

    if (isLoggedIn()) {
      router.replace('/')
    }
  }, [router])

  // ── Theme toggle ──────────────────────────────────────────
  function handleToggleTheme() {
    const next: Theme = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('lexvn-theme', next)
  }

  // ── Mode switch ───────────────────────────────────────────
  function handleModeChange(nextMode: Mode) {
    setMode(nextMode)
    setError('')
    setSuccess('')
  }

  // ── Submit ────────────────────────────────────────────────
  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (loading) return

    setError('')
    setSuccess('')

    if (!email.trim() || !password.trim()) {
      setError('Vui lòng nhập đầy đủ email và mật khẩu.')
      return
    }

    if (mode === 'register' && password.length < 8) {
      setError('Mật khẩu cần ít nhất 8 ký tự.')
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
    <div className="auth-layout">
      <AuthHero />

      <AuthPanel
        mode={mode}
        email={email}
        password={password}
        confirmPassword={confirmPassword}
        loading={loading}
        error={error}
        success={success}
        theme={theme}
        onModeChange={handleModeChange}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onConfirmPasswordChange={setConfirmPassword}
        onSubmit={handleSubmit}
        onToggleTheme={handleToggleTheme}
      />
    </div>
  )
}