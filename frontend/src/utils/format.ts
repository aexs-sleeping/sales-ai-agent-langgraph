/** Format a price value as ¥xx.xx. */
export function formatPrice(value: number | string | undefined | null): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return '—'
  return `¥${n.toFixed(2)}`
}

/** Format an ISO date string to a readable zh-CN timestamp. */
export function formatDate(value: string | undefined | null): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

/** Human label for order status (F9 tag colors are handled by components). */
export function orderStatusLabel(status: string | undefined): string {
  const map: Record<string, string> = {
    pending: '待处理',
    shipped: '已发货',
    cancelled: '已取消',
    completed: '已完成',
  }
  return status ? (map[status.toLowerCase()] ?? status) : '未知'
}
