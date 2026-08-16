import { defineStore } from 'pinia'

import { createConversation } from '@/api/client'
import { streamApprove, streamChat, streamDeny } from '@/api/sse'
import type {
  ChatMessage,
  PendingApproval,
  SSEHandlers,
  ToolStatus,
} from '@/types'
import {
  blocksFromToolResult,
  dedupeBlocks,
  parseStructuredBlocks,
} from '@/utils/parse'

let idCounter = 0
function nextId(): string {
  idCounter += 1
  return `msg-${Date.now()}-${idCounter}`
}

// Non-reactive stream bookkeeping (one active stream at a time). The message
// object reference avoids a per-token linear scan of the messages array.
let activeController: AbortController | null = null
let activeMessageId: string | null = null
let activeMessageObject: ChatMessage | null = null
let collectedResults: unknown[] = []

function extractToolResult(status: ToolStatus): unknown {
  if (status.result !== undefined && status.result !== null) return status.result
  const anyStatus = status as unknown as Record<string, unknown>
  for (const key of ['output', 'data']) {
    if (anyStatus[key] !== undefined && anyStatus[key] !== null)
      return anyStatus[key]
  }
  const args = status.args as Record<string, unknown> | undefined
  if (args) {
    for (const key of ['result', 'output']) {
      if (args[key] !== undefined && args[key] !== null) return args[key]
    }
  }
  return null
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversationId: null as string | null,
    messages: [] as ChatMessage[],
    pendingApproval: null as PendingApproval | null,
    streaming: false,
    toolStatus: null as ToolStatus | null,
    error: null as string | null,
    initializing: false,
  }),

  getters: {
    hasMessages: (state) => state.messages.length > 0,
  },

  actions: {
    async ensureConversation() {
      if (this.conversationId) return
      this.initializing = true
      try {
        this.conversationId = await createConversation()
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.initializing = false
      }
    },

    /** F13: start a brand-new conversation (new thread_id). */
    async newConversation() {
      this.resetChat()
      this.conversationId = null
      await this.ensureConversation()
    },

    /** F15: clear local chat, keep the current conversation. */
    clearConversation() {
      this.resetChat()
    },

    resetChat() {
      this.cancelStream()
      this.messages = []
      this.pendingApproval = null
      this.toolStatus = null
      this.error = null
    },

    cancelStream() {
      if (activeController) activeController.abort()
      this.resetActiveStream()
    },

    resetActiveStream() {
      this.streaming = false
      this.toolStatus = null
      activeMessageId = null
      activeMessageObject = null
      collectedResults = []
      activeController = null
    },

    /** Shared stream setup/teardown for chat / approve / deny (F2/F11). */
    async runStream(
      body: Record<string, unknown>,
      runner: (args: {
        body: Record<string, unknown>
        handlers: SSEHandlers
        signal?: AbortSignal
      }) => Promise<void>,
    ) {
      this.error = null
      this.pendingApproval = null
      this.streaming = true
      this.toolStatus = null
      const last = this.messages[this.messages.length - 1]
      activeMessageId = last?.id ?? null
      activeMessageObject = last ?? null
      collectedResults = []

      const controller = new AbortController()
      activeController = controller
      try {
        await runner({
          body,
          handlers: this.buildHandlers(),
          signal: controller.signal,
        })
      } catch (e) {
        if (!controller.signal.aborted)
          this.handleError(e instanceof Error ? e.message : String(e))
      }
    },

    /** F2/F3: send a message and consume the SSE reply. */
    async sendMessage(text: string) {
      const content = text.trim()
      if (!content || this.streaming) return
      await this.ensureConversation()
      if (!this.conversationId) return

      this.messages.push({
        id: nextId(),
        role: 'user',
        content,
        blocks: [],
        createdAt: Date.now(),
      })
      this.messages.push(this.newAssistantMessage())

      await this.runStream(
        {
          conversation_id: this.conversationId,
          message: content,
          // customer_id omitted → backend defaults to 123456789 (PRD §3.2)
        },
        streamChat,
      )
    },

    /** F11: approve the pending sensitive tool call. */
    async approve() {
      if (!this.conversationId || this.streaming || !this.pendingApproval) return
      const toolName = this.pendingApproval.tool_call.name
      this.cancelStream()
      this.pendingApproval = null

      this.pushSystemNote(`已批准工具调用「${toolName}」，继续执行…`)
      this.messages.push(this.newAssistantMessage())

      await this.runStream({ conversation_id: this.conversationId }, streamApprove)
    },

    /** F11/F12: deny the pending tool call with a reason. */
    async deny(reason: string) {
      if (!this.conversationId || this.streaming || !this.pendingApproval) return
      const toolName = this.pendingApproval.tool_call.name
      this.cancelStream()
      this.pendingApproval = null

      this.pushSystemNote(
        `已驳回工具调用「${toolName}」${reason ? `（原因：${reason}）` : ''}`,
      )
      this.messages.push(this.newAssistantMessage())

      await this.runStream(
        { conversation_id: this.conversationId, reason },
        streamDeny,
      )
    },

    newAssistantMessage(): ChatMessage {
      return {
        id: nextId(),
        role: 'assistant',
        content: '',
        blocks: [],
        toolCalls: [],
        streaming: true,
        createdAt: Date.now(),
      }
    },

    pushSystemNote(content: string) {
      this.messages.push({
        id: nextId(),
        role: 'system',
        content,
        blocks: [],
        createdAt: Date.now(),
      })
    },

    buildHandlers(): SSEHandlers {
      return {
        onMessage: (delta) => this.appendContent(delta),
        onToolStatus: (status) => this.handleToolStatus(status),
        onApprovalRequired: (approval) => this.handleApprovalRequired(approval),
        onDone: () => this.finalize(),
        onError: (message) => this.handleError(message),
      }
    },

    appendContent(delta: string) {
      if (activeMessageObject) activeMessageObject.content += delta
    },

    handleToolStatus(status: ToolStatus) {
      this.toolStatus = status
      const msg = activeMessageObject
      if (msg) {
        if (!msg.toolCalls) msg.toolCalls = []
        const idx = msg.toolCalls.findIndex((t) => t.name === status.name)
        if (idx !== -1) msg.toolCalls[idx] = status
        else msg.toolCalls.push(status)
      }
      if (status.status === 'success') {
        const result = extractToolResult(status)
        if (result !== null) collectedResults.push(result)
      }
    },

    handleApprovalRequired(approval: PendingApproval) {
      // The graph paused before the sensitive tool; the reply is complete.
      this.finalizeMessage(activeMessageId)
      this.pendingApproval = approval
      this.resetActiveStream()
    },

    finalize() {
      this.finalizeMessage(activeMessageId)
      this.resetActiveStream()
    },

    finalizeMessage(id: string | null) {
      const msg = activeMessageObject ?? (id ? this.messages.find((m) => m.id === id) : null)
      if (!msg) return
      msg.streaming = false
      const parsed = parseStructuredBlocks(msg.content)
      const toolBlocks = collectedResults
        .map((r) => blocksFromToolResult(r))
        .flat()
      msg.blocks = dedupeBlocks([...parsed, ...toolBlocks])
    },

    handleError(message: string) {
      this.error = message
      this.finalizeMessage(activeMessageId)
      this.resetActiveStream()
    },
  },
})
