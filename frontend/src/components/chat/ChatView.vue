<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import ApprovalCard from '@/components/approval/ApprovalCard.vue'
import { useChatStore } from '@/stores/chat'
import ChatMessage from './ChatMessage.vue'
import MessageInput from './MessageInput.vue'
import ToolStatusBar from './ToolStatusBar.vue'
import WelcomeEmpty from './WelcomeEmpty.vue'

const store = useChatStore()
const { messages, streaming, pendingApproval, toolStatus, hasMessages, error } =
  storeToRefs(store)

const listRef = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  messages,
  () => {
    scrollToBottom()
  },
  { deep: true },
)

function ask(text: string) {
  store.sendMessage(text)
}
</script>

<template>
  <div class="chat-view">
    <header class="chat-header">
      <div class="chat-header-title">
        <el-icon><ChatDotRound /></el-icon>
        <span>智购客服</span>
      </div>
      <div class="chat-header-status">
        <span class="online-dot" />
        {{ streaming ? '正在回复…' : '在线' }}
      </div>
    </header>

    <div v-if="error" class="chat-error">
      <el-alert type="error" :title="error" :closable="true" @close="store.error = null" show-icon />
    </div>

    <div ref="listRef" class="chat-scroll">
      <div class="chat-list">
        <template v-if="hasMessages">
          <ChatMessage
            v-for="m in messages"
            :key="m.id"
            :message="m"
            @ask="ask"
          />
        </template>
        <WelcomeEmpty v-else />

        <ApprovalCard v-if="pendingApproval" :approval="pendingApproval" />
      </div>
    </div>

    <ToolStatusBar v-if="streaming && toolStatus" :status="toolStatus" />

    <div class="chat-input-wrap">
      <MessageInput :disabled="streaming" @send="store.sendMessage" />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  background: var(--panel-bg);
  border-left: 1px solid var(--border);
  border-right: 1px solid var(--border);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-bg);
}

.chat-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: var(--text-main);
}

.chat-header-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-sub);
}

.chat-error {
  padding: 12px 20px 0;
}

.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
}

.chat-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

.chat-input-wrap {
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border);
  background: var(--panel-bg);
}

@media (max-width: 768px) {
  .chat-scroll {
    padding: 16px 12px;
  }
  .chat-input-wrap {
    padding: 10px 12px 12px;
  }
}
</style>
