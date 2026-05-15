export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

export interface ChatResponse {
  reply: string
  sources?: string[]
}

export async function sendMessage(content: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: content }),
  })

  if (!res.ok) {
    throw new Error('Chat request failed')
  }

  return res.json()
}