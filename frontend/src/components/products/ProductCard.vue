<script setup lang="ts">
import { computed } from 'vue'

import type { Product } from '@/types'
import { formatPrice } from '@/utils/format'

const props = defineProps<{ product: Product }>()
const emit = defineEmits<{ ask: [text: string] }>()

const stockLabel = computed(() => {
  const s = props.product.stock
  if (s <= 0) return '无货'
  if (s < 10) return `仅剩 ${s} 件`
  return `库存 ${s} 件`
})

function ask() {
  emit('ask', `我想看看这款商品：${props.product.name}`)
}
</script>

<template>
  <el-card class="product-card" shadow="hover" :body-style="{ padding: '14px' }">
    <div class="product-head">
      <span class="product-name" :title="product.name">{{ product.name }}</span>
      <el-tag v-if="product.recommended" type="warning" size="small" effect="light">
        为您推荐
      </el-tag>
    </div>
    <div class="product-category">{{ product.category }}</div>
    <div class="product-desc" :title="product.description">{{ product.description }}</div>
    <div class="product-foot">
      <span class="product-price">{{ formatPrice(product.price) }}</span>
      <span class="product-stock" :class="{ out: product.stock <= 0 }">{{ stockLabel }}</span>
    </div>
    <el-button
      class="product-ask-btn"
      size="small"
      type="primary"
      plain
      @click="ask"
    >
      看看这款
    </el-button>
  </el-card>
</template>

<style scoped>
.product-card {
  border-radius: 10px;
}

.product-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.product-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.product-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-category {
  font-size: 12px;
  color: var(--brand);
}

.product-desc {
  font-size: 12px;
  color: var(--text-sub);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 36px;
}

.product-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}

.product-price {
  font-size: 16px;
  font-weight: 700;
  color: #e02020;
}

.product-stock {
  font-size: 12px;
  color: #16a34a;
}

.product-stock.out {
  color: #dc2626;
}

.product-ask-btn {
  align-self: flex-start;
}
</style>
