<script setup lang="ts">
import { onMounted } from 'vue'

import ChatSidebar from '@/components/layout/ChatSidebar.vue'
import ChatView from '@/components/chat/ChatView.vue'
import { useChatStore } from '@/stores/chat'

const store = useChatStore()

onMounted(() => {
  // F13: obtain a conversation_id up front so the sidebar can show it.
  store.newConversation()
})
</script>

<template>
  <div class="app-shell">
    <ChatSidebar />
    <main class="app-main">
      <ChatView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
}

.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
</style>
