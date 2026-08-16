<script setup lang="ts">
import { computed } from 'vue'

import type { Order } from '@/types'
import { formatDate, formatPrice, orderStatusLabel } from '@/utils/format'

const props = defineProps<{ order: Order }>()

const statusType = computed<'success' | 'danger' | 'warning'>(() => {
  const s = props.order.status?.toLowerCase()
  if (s === 'shipped' || s === 'completed') return 'success'
  if (s === 'cancelled') return 'danger'
  return 'warning'
})

const itemsText = computed(() => {
  if (props.order.items && props.order.items.length) {
    return props.order.items
      .map((i) => `${i.name} × ${i.quantity}`)
      .join('、')
  }
  return props.order.products ?? ''
})
</script>

<template>
  <el-card class="order-card" :body-style="{ padding: '14px' }">
    <div class="order-head">
      <span class="order-id">订单号 #{{ order.order_id }}</span>
      <el-tag :type="statusType" size="small" effect="light">
        {{ orderStatusLabel(order.status) }}
      </el-tag>
    </div>
    <div v-if="order.order_date" class="order-date">
      {{ formatDate(order.order_date) }}
    </div>
    <div v-if="itemsText" class="order-items">{{ itemsText }}</div>
    <div class="order-total">
      合计：<span class="order-total-amount">{{ formatPrice(order.total_amount) }}</span>
    </div>
  </el-card>
</template>

<style scoped>
.order-card {
  border-radius: 10px;
  max-width: 460px;
}

.order-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.order-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.order-id {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-main);
}

.order-date {
  font-size: 12px;
  color: var(--text-sub);
}

.order-items {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.6;
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px 10px;
}

.order-total {
  font-size: 13px;
  color: var(--text-sub);
  text-align: right;
}

.order-total-amount {
  font-size: 16px;
  font-weight: 700;
  color: #e02020;
}
</style>
