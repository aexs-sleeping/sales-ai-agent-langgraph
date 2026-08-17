import type { MessageBlock, Order, Product } from '@/types'

/**
 * Converts structured tool results (carried by `tool_status(success).result`
 * per PRD §3.3) into renderable blocks.
 *
 * The backend serializes each tool's return value into the result field, so
 * the shapes here mirror the tool return shapes in backend/agent/tools.py:
 *   search_products                  -> { status, products: [...], metadata }
 *   search_products_recommendations  -> { status, recommendations: [...] }
 *   get_available_categories         -> { categories: [...] }           (no cards)
 *   check_order_status (single)      -> { status, order_id, order_date, order_status,
 *                                         products: "Name (x1), ...", total_amount }
 *   check_order_status (all)         -> { status, orders: [...] }
 *   create_order                     -> { order_id, status, total_amount,
 *                                         products: [{name, quantity, unit_price}] }
 */

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

/** Map one tool result payload to zero or more renderable blocks. */
export function blocksFromToolResult(result: unknown): MessageBlock[] {
  if (!isRecord(result)) return []
  if (Array.isArray(result.recommendations) && result.recommendations.length > 0) {
    return [
      {
        type: 'products',
        recommended: true,
        products: result.recommendations.map((p: any) => normalizeProduct(p, true)),
      },
    ]
  }
  if (Array.isArray(result.products)) {
    // Both search_products (product list) and create_order (order summary
    // items) use a `products` key; create_order also carries order_id.
    if (result.order_id != null) {
      return [{ type: 'order', order: normalizeOrder(result) }]
    }
    return [
      { type: 'products', products: result.products.map((p: any) => normalizeProduct(p)) },
    ]
  }
  if (Array.isArray(result.orders)) {
    return [{ type: 'orders', orders: result.orders.map((o: any) => normalizeOrder(o)) }]
  }
  // check_order_status single-order shape.
  if (result.order_id != null) {
    return [{ type: 'order', order: normalizeOrder(result) }]
  }
  return []
}

/** Normalize all tool results of one assistant reply into blocks. */
export function normalizeToolResults(results: unknown[]): MessageBlock[] {
  return results.flatMap(blocksFromToolResult)
}
