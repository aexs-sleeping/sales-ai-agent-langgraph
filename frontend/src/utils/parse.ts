import type { MessageBlock, Order, Product } from '@/types'

/**
 * Converts structured tool results (carried by `tool_status(success).result`
 * per PRD §3.3) into renderable blocks, dispatched by tool name.
 *
 * Tool return shapes mirror the return values in backend/agent/tools.py:
 *   search_products                  -> { status, products: [...], metadata }
 *   search_products_recommendations  -> { status, recommendations: [...] }
 *   check_order_status (single)      -> { status, order_id, order_date, order_status,
 *                                         products: "Name (x1), ...", total_amount }
 *   check_order_status (all)         -> { status, orders: [...] }
 *   create_order                     -> { order_id, status, total_amount,
 *                                         products: [{name, quantity, unit_price}] }
 *   get_available_categories         -> { categories: [...] }   (renders no cards)
 */

export interface ToolResultEntry {
  name: string
  result: unknown
}

function isRecord(v: unknown): v is Record<string, any> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function normalizeProduct(raw: Record<string, any>, recommended = false): Product {
  return {
    product_id: String(raw.product_id ?? ''),
    name: String(raw.name ?? ''),
    category: String(raw.category ?? ''),
    description: String(raw.description ?? ''),
    price: Number(raw.price ?? 0),
    stock: Number(raw.stock ?? 0),
    recommended,
  }
}

function normalizeOrder(raw: Record<string, any>): Order {
  return {
    order_id: String(raw.order_id ?? ''),
    order_date: raw.order_date,
    status: raw.status ?? raw.order_status,
    total_amount: raw.total_amount != null ? Number(raw.total_amount) : undefined,
    products: typeof raw.products === 'string' ? raw.products : undefined,
    items: Array.isArray(raw.products)
      ? raw.products.map((i: any) => ({
          name: String(i?.name ?? ''),
          quantity: Number(i?.quantity ?? 0),
          unit_price: i?.unit_price != null ? Number(i.unit_price) : undefined,
        }))
      : undefined,
    item_count: raw.item_count != null ? Number(raw.item_count) : undefined,
  }
}

/** Map one tool's result payload to zero or more renderable blocks. */
function blocksForTool(name: string, result: unknown): MessageBlock[] {
  if (!isRecord(result)) return []
  switch (name) {
    case 'search_products':
      return Array.isArray(result.products)
        ? [
            {
              type: 'products',
              products: result.products.map((p: any) => normalizeProduct(p)),
            },
          ]
        : []
    case 'search_products_recommendations':
      return Array.isArray(result.recommendations)
        ? [
            {
              type: 'products',
              products: result.recommendations.map((p: any) => normalizeProduct(p, true)),
            },
          ]
        : []
    case 'check_order_status':
      // All-orders query returns an `orders` list; the single-order query
      // returns one order object directly.
      if (Array.isArray(result.orders)) {
        return [
          { type: 'orders', orders: result.orders.map((o: any) => normalizeOrder(o)) },
        ]
      }
      return result.order_id != null
        ? [{ type: 'order', order: normalizeOrder(result) }]
        : []
    case 'create_order':
      return result.order_id != null
        ? [{ type: 'order', order: normalizeOrder(result) }]
        : []
    default:
      // get_available_categories and any unknown tools render no cards.
      return []
  }
}

/** Normalize the collected tool results of one assistant reply into blocks. */
export function normalizeToolResults(entries: ToolResultEntry[]): MessageBlock[] {
  return entries.flatMap(({ name, result }) => blocksForTool(name, result))
}
