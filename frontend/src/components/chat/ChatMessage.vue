<script setup lang="ts">
import { computed } from 'vue'

import OrderCard from '@/components/orders/OrderCard.vue'
import ProductCard from '@/components/products/ProductCard.vue'
import type { ChatMessage as ChatMessageType, ToolStatus } from '@/types'
import { toolLabel } from '@/utils/toolLabels'

const props = defineProps<{ message: ChatMessageType }>()
const emit = defineEmits<{ ask: [text: string] }>()

const isUser = computed(() => props.message.role === 'user')
const isSystem = computed(() => props.message.role === 'system')

function tagType(status: ToolStatus['status']): 'success' | 'danger' | 'info' {
  if (status === 'success') return 'success'
  if (status === 'error') return 'danger'
  return 'info'
}

function forwardAsk(text: string) {
  emit('ask', text)
}
</script>

<template>
  <!-- System note (approval feedback etc.) -->
  <div v-if="isSystem" class="msg-system">{{ message.content }}</div>

  <div v-else class="msg-row" :class="isUser ? 'msg-user' : 'msg-assistant'">
    <div v-if="!isUser" class="avatar">
      <el-icon :size="16"><Service /></el-icon>
    </div>

    <div class="bubble">
      <div v-if="message.content" class="bubble-text" :class="{ streaming: message.streaming }">
        {{ message.content }}
        <span v-if="message.streaming" class="caret" />
      </div>
      <div v-else-if="message.streaming" class="bubble-text thinking">
        正在思考…
      </div>

      <!-- Structured cards (F5/F7/F8/F9) -->
      <template v-for="(block, i) in message.blocks" :key="i">
        <div v-if="block.type === 'products'" class="block">
          <div v-if="block.recommended" class="block-title">为您推荐</div>
          <div class="product-grid">
            <ProductCard
              v-for="p in block.products"
              :key="p.product_id || p.name"
              :product="p"
              @ask="forwardAsk"
            />
          </div>
        </div>
        <div v-else-if="block.type === 'order'" class="block">
          <OrderCard :order="block.order" />
        </div>
        <div v-else-if="block.type === 'orders'" class="block">
          <OrderCard v-for="o in block.orders" :key="o.order_id" :order="o" />
        </div>
      </template>

      <!-- Tool lifecycle trace (F4) -->
      <div v-if="message.toolCalls && message.toolCalls.length" class="tool-trace">
        <el-tag
          v-for="(t, i) in message.toolCalls"
          :key="`${t.name}-${i}`"
          size="small"
          :type="tagType(t.status)"
          effect="light"
        >
          {{ toolLabel(t.name) }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.msg-user {
  flex-direction: row-reverse;
}

.msg-system {
  align-self: center;
  font-size: 12px;
  color: var(--text-sub);
  background: #f3f4f6;
  border-radius: 999px;
  padding: 4px 14px;
  max-width: 80%;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bubble {
  max-width: 76%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bubble-text {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-user .bubble-text {
  background: var(--brand);
  color: #fff;
  border-top-right-radius: 4px;
}

.msg-assistant .bubble-text {
  background: #f2f4f7;
  color: var(--text-main);
  border-top-left-radius: 4px;
}

.caret {
  display: inline-block;
  width: 2px;
  height: 15px;
  background: var(--brand);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.9s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.thinking {
  color: var(--text-sub);
}

.block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.block-title {
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.tool-trace {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
