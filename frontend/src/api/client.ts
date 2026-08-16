/**
 * REST helpers for the FastAPI backend (PRD §3.2).
 * `/api` is proxied to http://localhost:8000 in dev (see vite.config.ts).
 */
const API_BASE = '/api'

/** Shared non-2xx error parser (also used by the SSE transport in sse.ts). */
export async function parseError(res: Response): Promise<Error> {
  let detail = res.statusText
  try {
    const data = await res.json()
    if (data && data.detail) detail = data.detail
  } catch {
    /* response body was not JSON */
  }
  return new Error(`请求失败（HTTP ${res.status}）：${detail}`)
}

/** POST /api/conversations → { status, conversation_id } */
export async function createConversation(): Promise<string> {
  const res = await fetch(`${API_BASE}/conversations`, { method: 'POST' })
  if (!res.ok) throw await parseError(res)
  const data = (await res.json()) as { conversation_id?: string }
  if (!data.conversation_id) throw new Error('创建会话失败：响应缺少 conversation_id')
  return data.conversation_id
}
