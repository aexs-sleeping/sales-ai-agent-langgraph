import type { MessageBlock, Order, Product } from '@/types'

/**
 * Best-effort extraction of structured product / order data.
 *
 * The SSE contract (PRD §3.3) streams AI text tokens and tool lifecycle events
 * but does not carry tool *results* on the wire, so the frontend reconstructs
 * structured cards from two sources:
 *   1. JSON blocks embedded in the assistant's reply (```json ... ``` or a
 *      single top-level object).
 *   2. An optional `result`/`output` field the backend may attach to
 *      `tool_status(success)` events (tolerated, harmless if absent).
 */

function isRecord(v: unknown): v is Record<string, any> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function isProduct(v: unknown): v is Record<string, any> {
  return (
    isRecord(v) &&
    typeof v.name === 'string' &&
    (typeof v.price === 'number' || typeof v.price === 'string')
  )
}

function isOrder(v: unknown): v is Record<string, any> {
  return (
    isRecord(v) &&
    (typeof v.order_id === 'string' ||
      typeof v.order_id === 'number' ||
      typeof v.orderId === 'string' ||
      typeof v.orderId === 'number')
  )
}

function normalizeProduct(raw: Record<string, any>, recommended = false): Product {
  return {
    product_id: String(
      raw.product_id ?? raw.productId ?? raw.ProductId ?? raw.id ?? '',
    ),
    name: String(raw.name ?? raw.ProductName ?? raw.product_name ?? ''),
    category: String(raw.category ?? raw.Category ?? ''),
    description: String(raw.description ?? raw.Description ?? ''),
    price: Number(raw.price ?? raw.Price ?? 0),
    stock: Number(raw.stock ?? raw.quantity ?? raw.Quantity ?? 0),
    recommended,
  }
}

function normalizeOrder(raw: Record<string, any>): Order {
  const toItems = (list: unknown): Order['items'] =>
    Array.isArray(list)
      ? list.map((i) => {
          const r = isRecord(i) ? i : {}
          return {
            name: String(r.name ?? r.ProductName ?? r.product_name ?? ''),
            quantity: Number(r.quantity ?? r.Quantity ?? 0),
            unit_price:
              r.unit_price != null
                ? Number(r.unit_price)
                : r.UnitPrice != null
                  ? Number(r.UnitPrice)
                  : undefined,
          }
        })
      : undefined

  const items =
    toItems(raw.items) ?? toItems(raw.products && typeof raw.products !== 'string' ? raw.products : undefined)

  return {
    order_id: String(
      raw.order_id ?? raw.orderId ?? raw.OrderId ?? raw.id ?? '',
    ),
    order_date: raw.order_date ?? raw.orderDate ?? raw.OrderDate ?? undefined,
    status: raw.status ?? raw.order_status ?? raw.Status ?? undefined,
    total_amount:
      raw.total_amount != null
        ? Number(raw.total_amount)
        : raw.totalAmount != null
          ? Number(raw.totalAmount)
          : raw.TotalAmount != null
            ? Number(raw.TotalAmount)
            : undefined,
    products:
      typeof raw.products === 'string' ? String(raw.products) : undefined,
    items,
    item_count:
      raw.item_count != null
        ? Number(raw.item_count)
        : raw.itemCount != null
          ? Number(raw.itemCount)
          : undefined,
  }
}

function extractJsonValues(text: string): unknown[] {
  const values: unknown[] = []
  const fenced = /```(?:json)?\s*([\s\S]*?)```/gi
  let m: RegExpExecArray | null
  while ((m = fenced.exec(text)) !== null) {
    try {
      values.push(JSON.parse(m[1]))
    } catch {
      /* skip malformed fenced block */
    }
  }
  const stripped = text.replace(fenced, '')
  // Best-effort single top-level object in the remaining text.
  const start = stripped.indexOf('{')
  const end = stripped.lastIndexOf('}')
  if (start !== -1 && end > start) {
    try {
      values.push(JSON.parse(stripped.slice(start, end + 1)))
    } catch {
      /* skip malformed inline object */
    }
  }
  return values
}

/** Extract structured blocks (products / orders) from assistant text. */
export function parseStructuredBlocks(content: string): MessageBlock[] {
  const blocks: MessageBlock[] = []
  for (const value of extractJsonValues(content)) {
    if (Array.isArray(value)) {
      if (value.length > 0 && value.every(isProduct)) {
        blocks.push({
          type: 'products',
          products: value.map((p) => normalizeProduct(p)),
        })
      } else if (value.length > 0 && value.every(isOrder)) {
        blocks.push({
          type: 'orders',
          orders: value.map((o) => normalizeOrder(o)),
        })
      }
    } else if (isRecord(value)) {
      if (Array.isArray(value.recommendations)) {
        blocks.push({
          type: 'products',
          recommended: true,
          products: value.recommendations.map((p) => normalizeProduct(p, true)),
        })
      } else if (Array.isArray(value.products)) {
        blocks.push({
          type: 'products',
          products: value.products.map((p) => normalizeProduct(p)),
        })
      } else if (value.order && isRecord(value.order)) {
        blocks.push({ type: 'order', order: normalizeOrder(value.order) })
      } else if (Array.isArray(value.orders)) {
        blocks.push({
          type: 'orders',
          orders: value.orders.map((o) => normalizeOrder(o)),
        })
      } else if (isProduct(value)) {
        blocks.push({ type: 'products', products: [normalizeProduct(value)] })
      } else if (isOrder(value)) {
        blocks.push({ type: 'order', order: normalizeOrder(value) })
      }
    }
  }
  return blocks
}

/** Convert a tool `result` payload (if the backend provides one) to blocks. */
export function blocksFromToolResult(result: unknown): MessageBlock[] {
  if (!result) return []
  if (isRecord(result) || Array.isArray(result)) {
    return parseStructuredBlocks(JSON.stringify(result))
  }
  return []
}

/** Remove duplicate blocks (by product_id / order_id) so cards render once. */
export function dedupeBlocks(blocks: MessageBlock[]): MessageBlock[] {
  const seenProducts = new Set<string>()
  const seenOrders = new Set<string>()
  const out: MessageBlock[] = []
  for (const block of blocks) {
    if (block.type === 'products') {
      const fresh = block.products.filter((p) => {
        const key = p.product_id || `${p.name}|${p.price}`
        if (seenProducts.has(key)) return false
        seenProducts.add(key)
        return true
      })
      if (fresh.length > 0) out.push({ ...block, products: fresh })
    } else if (block.type === 'order') {
      const key = block.order.order_id
      if (key && seenOrders.has(key)) continue
      if (key) seenOrders.add(key)
      out.push(block)
    } else if (block.type === 'orders') {
      const fresh = block.orders.filter((o) => {
        const key = o.order_id
        if (!key) return true
        if (seenOrders.has(key)) return false
        seenOrders.add(key)
        return true
      })
      if (fresh.length > 0) out.push({ ...block, orders: fresh })
    }
  }
  return out
}
