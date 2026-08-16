/**
 * Tool name → Chinese display label, the single source of truth shared by the
 * approval card, message tool-trace tags, and the live tool status bar (F4/F10).
 * Keep in sync with the tool names in backend/agent/tools.py.
 */

export const TOOL_LABELS: Record<string, string> = {
  get_available_categories: '查询分类',
  search_products: '搜索商品',
  search_products_recommendations: '商品推荐',
  check_order_status: '查询订单',
  create_order: '创建订单',
}

/** "正在…" progress phrasing used by the live tool status bar (F4). */
const TOOL_ACTIVE_LABELS: Record<string, string> = {
  get_available_categories: '正在查询商品分类',
  search_products: '正在搜索商品',
  search_products_recommendations: '正在为您生成推荐',
  check_order_status: '正在查询订单',
  create_order: '正在创建订单',
}

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name
}

export function activeToolLabel(name: string): string {
  return TOOL_ACTIVE_LABELS[name] ?? `正在调用工具 ${name}`
}
