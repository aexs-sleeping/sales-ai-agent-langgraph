<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { useChatStore } from '@/stores/chat'
import type { PendingApproval } from '@/types'
import { toolLabel } from '@/utils/toolLabels'

const props = defineProps<{ approval: PendingApproval }>()

const store = useChatStore()

const showDenyDialog = ref(false)
const denyReason = ref('')
const submitting = ref(false)

const toolArgsJson = computed(() =>
  JSON.stringify(props.approval.tool_call.args, null, 2),
)

const label = computed(() => toolLabel(props.approval.tool_call.name))

async function onApprove() {
  submitting.value = true
  try {
    await store.approve()
    ElMessage.success('已批准，正在继续执行')
  } catch {
    /* store surfaces the error */
  } finally {
    submitting.value = false
  }
}

async function onDeny() {
  showDenyDialog.value = false
  submitting.value = true
  try {
    await store.deny(denyReason.value.trim())
    ElMessage.warning('已驳回该操作')
  } catch {
    /* store surfaces the error */
  } finally {
    submitting.value = false
    denyReason.value = ''
  }
}
</script>

<template>
  <div class="approval-wrap">
    <el-card class="approval-card" :body-style="{ padding: '16px' }">
      <div class="approval-title">
        <el-icon color="#E6A23C"><WarningFilled /></el-icon>
        <span>需要人工审批</span>
      </div>

      <div class="approval-tool">
        AI 想执行敏感操作：<b>{{ label }}</b>
        <span class="approval-tool-name">{{ approval.tool_call.name }}</span>
      </div>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="该操作（下单）需要人工确认后才会真正执行"
      />

      <div class="approval-args">
        <pre>{{ toolArgsJson }}</pre>
      </div>

      <div class="approval-actions">
        <el-button type="primary" :loading="submitting" @click="onApprove">
          批准
        </el-button>
        <el-button type="danger" plain :loading="submitting" @click="showDenyDialog = true">
          驳回
        </el-button>
      </div>
    </el-card>

    <el-dialog
      v-model="showDenyDialog"
      title="驳回原因"
      width="420px"
      append-to-body
    >
      <el-input
        v-model="denyReason"
        type="textarea"
        :rows="3"
        placeholder="请输入驳回原因（可选）"
      />
      <template #footer>
        <el-button @click="showDenyDialog = false">取消</el-button>
        <el-button type="danger" @click="onDeny">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.approval-wrap {
  align-self: center;
  width: 100%;
  max-width: 560px;
}

.approval-card {
  border-radius: 12px;
  border-color: #f5d5a0;
  background: #fffdf7;
}

.approval-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.approval-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #92400e;
}

.approval-tool {
  font-size: 14px;
  color: var(--text-main);
}

.approval-tool-name {
  margin-left: 8px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  color: var(--text-sub);
  background: #f3f4f6;
  border-radius: 4px;
  padding: 2px 6px;
}

.approval-args {
  background: #1f2937;
  color: #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
}

.approval-args pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  font-family: ui-monospace, Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.approval-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}
</style>
