<script setup lang="ts">
import { useChatStore } from '@/stores/chat'

const store = useChatStore()

const suggestions = [
  '有哪些商品可以买？',
  '帮我搜索水果，价格在 20 元以内',
  '查看我的订单',
  '给我推荐一些商品',
]

function ask(text: string) {
  store.sendMessage(text)
}
</script>

<template>
  <div class="welcome">
    <div class="welcome-avatar">
      <el-icon :size="34"><Service /></el-icon>
    </div>
    <h2 class="welcome-title">你好，我是智购小助手</h2>
    <p class="welcome-desc">
      可以帮你找商品、下单、查订单，还会根据你的偏好做推荐。想从哪儿开始？
    </p>
    <div class="suggestions">
      <el-button
        v-for="s in suggestions"
        :key="s"
        round
        plain
        type="primary"
        @click="ask(s)"
      >
        {{ s }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px 16px;
  gap: 12px;
}

.welcome-avatar {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1e6fff, #5aa2ff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
  box-shadow: 0 8px 20px rgba(30, 111, 255, 0.25);
}

.welcome-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-main);
  margin: 0;
}

.welcome-desc {
  font-size: 14px;
  color: var(--text-sub);
  margin: 0 0 12px;
  max-width: 420px;
  line-height: 1.7;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 480px;
}
</style>
