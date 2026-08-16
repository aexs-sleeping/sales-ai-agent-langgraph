import { fetchEventSource } from '@microsoft/fetch-event-source'

import { parseError } from '@/api/client'
import type { PendingApproval, SSEHandlers, ToolStatus } from '@/types'

const API_BASE = '/api'

export interface RunStreamArgs {
  url: string
  body: Record<string, unknown>
  handlers: SSEHandlers
  signal?: AbortSignal
}

/** Error thrown by onopen for non-2xx responses so we can surface a friendly message. */
class SseRequestError extends Error {}

function parsePayload(data: string): any {
  if (!data) return {}
  try {
    return JSON.parse(data)
  } catch {
    return { content: data }
  }
}

function conversationUrl(id: unknown, action: 'approve' | 'deny'): string {
  return `${API_BASE}/conversations/${encodeURIComponent(String(id))}/${action}`
}

/**
 * POST + SSE transport shared by chat / approve / deny (PRD §3.3).
 *
 * Event dispatch:
 *   message           → handlers.onMessage(content)
 *   tool_status       → handlers.onToolStatus({name,status,args,result?})
 *   approval_required → handlers.onApprovalRequired({tool_call})
 *   done              → handlers.onDone()
 *   error             → handlers.onError(message)
 *
 * All failures are normalized here and delivered via handlers.onError exactly
 * once; the returned promise resolves normally so callers don't double-handle.
 */
export async function runSSEStream({
  url,
  body,
  handlers,
  signal,
}: RunStreamArgs): Promise<void> {
  try {
    await fetchEventSource(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(body),
      signal,
      openWhenHidden: true,

      async onopen(response) {
        if (response.ok) return
        // Non-2xx: surface a friendly error and stop (no retry).
        throw new SseRequestError((await parseError(response)).message)
      },

      onmessage(message) {
        const type = message.event || 'message'
        const payload = parsePayload(message.data)
        switch (type) {
          case 'message':
            handlers.onMessage(String(payload.content ?? ''))
            break
          case 'tool_status':
            handlers.onToolStatus(payload as ToolStatus)
            break
          case 'approval_required':
            handlers.onApprovalRequired(payload as PendingApproval)
            break
          case 'done':
            handlers.onDone()
            break
          case 'error':
            handlers.onError(String(payload.message ?? '服务出错，请重试。'))
            break
          default:
            // Ignore unknown event types so the contract can evolve.
            break
        }
      },

      onerror(error) {
        // This callback is synchronous. Returning a value would make the
        // library retry forever; throwing stops the stream.
        throw error
      },
    })
  } catch (error) {
    // Abort is expected when switching/clearing a conversation.
    if (signal?.aborted) return
    if (error instanceof SseRequestError) {
      handlers.onError(error.message)
      return
    }
    handlers.onError('网络连接中断，请重试。')
  }
}

/** POST /api/chat — send a message and consume the SSE reply. */
export function streamChat(args: Omit<RunStreamArgs, 'url'>): Promise<void> {
  return runSSEStream({
    ...args,
    url: `${API_BASE}/chat`,
    body: {
      conversation_id: args.body.conversation_id,
      message: args.body.message,
      customer_id: args.body.customer_id,
    },
  })
}

/** POST /api/conversations/{id}/approve — resume from the HITL interrupt. */
export function streamApprove(args: Omit<RunStreamArgs, 'url'>): Promise<void> {
  return runSSEStream({
    ...args,
    url: conversationUrl(args.body.conversation_id, 'approve'),
    body: {},
  })
}

/** POST /api/conversations/{id}/deny — deny with a reason. */
export function streamDeny(args: Omit<RunStreamArgs, 'url'>): Promise<void> {
  return runSSEStream({
    ...args,
    url: conversationUrl(args.body.conversation_id, 'deny'),
    body: { reason: args.body.reason },
  })
}
