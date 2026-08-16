<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')

function submit() {
  const value = text.value.trim()
  if (!value) return
  emit('send', value)
  text.value = ''
}

function onKeydown(e: KeyboardEvent) {
  // Enter sends, Shift+Enter inserts a newline (PRD F2).
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="message-input">
    <el-input
      v-model="text"
      type="textarea"
      :rows="2"
      :disabled="disabled"
      :placeholder="
        disabled ? '正在回复中…' : '输入消息，Enter 发送，Shift+Enter 换行'
      "
      resize="none"
      class="message-input-textarea"
      @keydown="onKeydown"
    />
    <el-button
      type="primary"
      class="send-btn"
      :disabled="disabled || !text.trim()"
      @click="submit"
    >
      <el-icon class="send-icon"><Promotion /></el-icon>
      发送
    </el-button>
  </div>
</template>

<style scoped>
.message-input {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.message-input-textarea {
  flex: 1;
}

.send-btn {
  height: 40px;
  padding: 0 20px;
  flex-shrink: 0;
}

.send-icon {
  margin-right: 4px;
}
</style>
