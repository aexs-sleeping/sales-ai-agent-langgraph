/**
 * Shared domain types for the Virtual Sales Agent frontend.
 * Shapes follow docs/PRD.md §2 + §3.3 and the backend tools in backend/agent/tools.py.
 */

export type Role = 'user' | 'assistant' | 'system'

/** Structured blocks rendered inside an assistant message. */
export type MessageBlock =
  | { type: 'products'; products: Product[] }
  | { type: 'order'; order: Order }
  | { type: 'orders'; orders: Order[] }

export interface ChatMessage {
  id: string
  role: Role
  /** Accumulated plain-text content (typewriter while streaming). */
  content: string
  /** Structured blocks extracted from content / tool results. */
  blocks: MessageBlock[]
  /** Tools invoked while producing this reply (lifecycle trace, F4). */
  toolCalls?: ToolStatus[]
  streaming?: boolean
  createdAt: number
}

export interface Product {
  product_id: string
  name: string
  category: string
  description: string
  price: number
  stock: number
  /** Set when rendered as a recommendation (F8). */
  recommended?: boolean
}

export interface OrderItem {
  name: string
  quantity: number
  unit_price?: number
}

export interface Order {
  order_id: string
  order_date?: string
  status?: string
  total_amount?: number
  /** From check_order_status single-order query: "Name (x2), Other (x1)". */
  products?: string
  items?: OrderItem[]
  item_count?: number
}

export interface ToolCallInfo {
  id: string
  name: string
  args: Record<string, any>
}

export type ToolStatusKind = 'running' | 'success' | 'error'

export interface ToolStatus {
  name: string
  status: ToolStatusKind
  args?: Record<string, any>
  /** Tool's structured JSON output, carried on success (PRD §3.3). */
  result?: unknown
}

export interface PendingApproval {
  tool_call: ToolCallInfo
}

export interface SSEHandlers {
  onMessage: (content: string) => void
  onToolStatus: (status: ToolStatus) => void
  onApprovalRequired: (approval: PendingApproval) => void
  onDone: () => void
  onError: (message: string) => void
}
