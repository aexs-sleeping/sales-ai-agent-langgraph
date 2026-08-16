<script setup lang="ts">
import { computed } from 'vue'

import type { ToolStatus } from '@/types'
import { activeToolLabel } from '@/utils/toolLabels'

const props = defineProps<{ status: ToolStatus }>()

const label = computed(() => activeToolLabel(props.status.name))
const running = computed(() => props.status.status === 'running')
</script>

<template>
  <div class="tool-status-bar" :class="`status-${status.status}`">
    <el-icon v-if="running" class="is-loading"><Loading /></el-icon>
    <el-icon v-else-if="status.status === 'success'"><CircleCheck /></el-icon>
    <el-icon v-else><CircleClose /></el-icon>
    <span>{{ label }}</span>
    <span v-if="status.status === 'error'" class="tool-status-err">（执行出错）</span>
  </div>
</template>

<style scoped>
.tool-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 20px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-sub);
  background: #f3f4f6;
}

.status-running {
  color: var(--brand);
  background: var(--brand-light);
}

.status-success {
  color: #16a34a;
  background: #f0fdf4;
}

.status-error {
  color: #dc2626;
  background: #fef2f2;
}

.tool-status-err {
  font-weight: 600;
}
</style>
