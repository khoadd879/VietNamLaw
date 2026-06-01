export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
export const TOKEN_KEY = 'lexvn-token'
export const SESSION_KEY = 'lexvn-session-id'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

export interface ChatResponse {
  reply: string
  sources?: string[]
}

export interface AuthResponse {
  id: string
  email: string
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: string
  email: string
}

export interface SessionResponse {
  id: string
  user_id: string
  title: string
}

export interface MessageResponse {
  id: string
  session_id: string
  user_id: string
  role: string
  content: string
  sources_json: Record<string, unknown> | null
}

export function getToken(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(TOKEN_KEY, token)
  }
}

export function getStoredSessionId(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return localStorage.getItem(SESSION_KEY)
}

export function setStoredSessionId(sessionId: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem(SESSION_KEY, sessionId)
  }
}

export function clearStoredSessionId(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(SESSION_KEY)
  }
}

export function clearAuthState(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(SESSION_KEY)
    localStorage.removeItem('lexvn-user-email')
    localStorage.removeItem('lexvn-user-id')
  }
}

function getAuthHeaders(): HeadersInit {
  const token = getToken()

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json()
    return data?.detail || fallback
  } catch {
    return fallback
  }
}

export function storeAuthState(auth: AuthResponse): void {
  setToken(auth.access_token)

  if (typeof window !== 'undefined') {
    localStorage.setItem('lexvn-user-email', auth.email)
    localStorage.setItem('lexvn-user-id', auth.id)
  }
}

export function isLoggedIn(): boolean {
  return Boolean(getToken())
}

export function logout(): void {
  clearAuthState()
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Đăng ký thất bại'))
  }

  return res.json()
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Đăng nhập thất bại'))
  }

  return res.json()
}

export async function getMe(): Promise<UserResponse> {
  const res = await fetch(`${API_URL}/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể lấy thông tin tài khoản'))
  }

  return res.json()
}

export async function createSession(title?: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/chat/sessions`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ title }),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể tạo phiên chat'))
  }

  return res.json()
}

export async function listSessions(): Promise<SessionResponse[]> {
  const res = await fetch(`${API_URL}/chat/sessions`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể tải danh sách phiên chat'))
  }

  return res.json()
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể lấy thông tin phiên chat'))
  }

  return res.json()
}

export async function renameSession(sessionId: string, title: string): Promise<SessionResponse> {
  const res = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    body: JSON.stringify({ title }),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể đổi tên phiên chat'))
  }

  return res.json()
}

export async function deleteSession(sessionId: string): Promise<boolean> {
  const res = await fetch(`${API_URL}/chat/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể xóa phiên chat'))
  }

  const data = await res.json()
  return Boolean(data?.deleted)
}

export async function getMessages(sessionId: string): Promise<MessageResponse[]> {
  const res = await fetch(`${API_URL}/chat/sessions/${sessionId}/messages`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể tải lịch sử phiên chat'))
  }

  return res.json()
}

export async function sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ session_id: sessionId, message }),
  })

  if (!res.ok) {
    throw new Error(await readError(res, 'Không thể gửi yêu cầu chat'))
  }

  return res.json()
}

export function mapMessageHistory(messages: MessageResponse[]): ChatMessage[] {
  return messages.map((message) => ({
    role: message.role === 'user' ? 'user' : 'assistant',
    content: message.content,
    sources: Array.isArray(message.sources_json?.sources)
      ? (message.sources_json?.sources as string[])
      : undefined,
  }))
}

export async function ensureSession(): Promise<string> {
  const stored = getStoredSessionId()
  if (stored) {
    return stored
  }

  const session = await createSession()
  setStoredSessionId(session.id)
  return session.id
}

export async function loadSessionHistory(): Promise<ChatMessage[]> {
  const sessionId = getStoredSessionId()
  if (!sessionId) {
    return []
  }

  const messages = await getMessages(sessionId)
  return mapMessageHistory(messages)
}

export async function resetSession(): Promise<string> {
  clearStoredSessionId()
  return ensureSession()
}

export async function sendAuthedMessage(message: string): Promise<ChatResponse> {
  const sessionId = await ensureSession()
  return sendMessage(sessionId, message)
}

export function summarizeSessionPreview(messages: ChatMessage[]): string {
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  const basis = lastAssistant?.content || lastUser?.content || 'Chưa có nội dung'
  return basis.replace(/\s+/g, ' ').trim().slice(0, 88)
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof Error && /Unauthorized|401/i.test(error.message)
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof Error && /Session not found|404/i.test(error.message)
}
