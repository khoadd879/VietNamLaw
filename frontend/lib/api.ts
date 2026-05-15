export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function sendMessage(content: string) {
  return { reply: "stub" }
}