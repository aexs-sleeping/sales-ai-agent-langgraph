<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

import { useChatStore } from '@/stores/chat'

const store = useChatStore()
const { conversationId, streaming } = storeToRefs(store)

function newChat() {
  store.newConversation()
}

function clearChat() {
  store.clearConversation()
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-logo">
        <el-icon :size="20"><ShoppingBag /></el-icon>
      </div>
      <div class="brand-text">
        <div class="brand-name">智购客服</div>
        <div class="brand-sub">Virtual Sales Agent</div>
      </div>
    </div>

    <el-button
      class="new-chat-btn"
      type="primary"
      size="large"
      :icon="Plus"
      :disabled="streaming"
      @click="newChat"
    >
      新建会话
    </el-button>

    <div class="sidebar-section">
      <div class="sidebar-title">客服信息</div>
      <div class="agent-card">
        <div class="agent-avatar">
          <el-icon :size="18"><Service /></el-icon>
        </div>
        <div class="agent-info">
          <div class="agent-name">智购小助手</div>
          <div class="agent-online">
            <span class="online-dot" />
            在线
          </div>
        </div>
      </div>
      <p class="agent-desc">可以帮你找商品、下单、查订单、获取个性化推荐。</p>
    </div>

    <div class="sidebar-section">
      <div class="sidebar-title">会话</div>
      <div class="conv-meta">
        <div class="conv-id" :title="conversationId || ''">
          会话 ID：{{ conversationId || '—' }}
        </div>
      </div>
      <el-button
        class="clear-btn"
        text
        type="danger"
        :disabled="streaming"
        @click="clearChat"
      >
        清空会话
      </el-button>
    </div>

    <div class="sidebar-footer">Powered by LangGraph · Gemini</div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 264px;
  flex-shrink: 0;
  background: var(--panel-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  height: 100%;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.brand-logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-name {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.2;
}

.brand-sub {
  font-size: 12px;
  color: var(--text-sub);
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 20px;
}

.sidebar-section {
  margin-bottom: 20px;
}

.sidebar-title {
  font-size: 12px;
  color: var(--text-sub);
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--brand-light);
  border-radius: 10px;
  padding: 10px 12px;
}

.agent-avatar {
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

.agent-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-main);
}

.agent-online {
  font-size: 12px;
  color: #16a34a;
  display: flex;
  align-items: center;
  gap: 4px;
}

.agent-desc {
  font-size: 12px;
  color: var(--text-sub);
  line-height: 1.6;
  margin: 10px 0 0;
}

.conv-meta {
  font-size: 12px;
  color: var(--text-sub);
}

.conv-id {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.clear-btn {
  margin-top: 6px;
  padding-left: 0;
}

.sidebar-footer {
  margin-top: auto;
  font-size: 11px;
  color: #9ca3af;
  text-align: center;
}
</style>
