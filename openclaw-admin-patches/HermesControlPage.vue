<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import {
  NButton, NCard, NIcon, NInput, NSpace, NText, NSpin, NAlert, NTag, NDivider, NEmpty, NProgress
} from 'naive-ui'
import { SendOutline, TerminalOutline, TimeOutline, PlayOutline, StopOutline } from '@vicons/ionicons5'
import { renderSimpleMarkdown } from '@/utils/markdown'

const API = 'http://172.25.0.12:9000'
const message = ref('')
const loading = ref(false)
const error = ref('')
const autoRunning = ref(false)
const autoProgress = ref(0)
const autoCountdown = ref(0)
let autoTimer: any = null
let countdownTimer: any = null
let autoIndex = 0

const DEMO_TASKS = [
  '請用 terminal 查詢系統負載與記憶體使用狀況，整理成報告',
  '請用 terminal 查詢磁碟使用狀況，告訴我哪個分割區快滿了',
  '請用 terminal 查詢目前網路介面狀態與 IP',
  '請用 terminal 查詢最近 10 筆系統日誌（journalctl）',
  '請用 terminal 查詢目前所有 python 進程',
]
const INTERVAL = 45

interface HistoryItem {
  id: number
  command: string
  text: string
  tool_calls: string[]
  timestamp: string
  elapsed: number
}
const history = ref<HistoryItem[]>([])
let idCounter = 0

async function execCommand(cmd?: string) {
  const task = cmd || message.value.trim()
  if (!task || loading.value) return
  loading.value = true
  error.value = ''
  const t0 = Date.now()
  try {
    const r = await fetch(`${API}/api/hermes-exec`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: task })
    })
    const d = await r.json()
    if (d.error) {
      error.value = d.error
    } else {
      history.value.unshift({
        id: idCounter++,
        command: task,
        text: d.text || '',
        tool_calls: d.tool_calls || [],
        timestamp: new Date().toLocaleTimeString('zh-TW'),
        elapsed: Math.round((Date.now() - t0) / 1000)
      })
      if (!cmd) message.value = ''
    }
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startAutoDemo() {
  autoRunning.value = true
  autoIndex = 0
  runNextAuto()
}

async function runNextAuto() {
  if (!autoRunning.value) return
  const task = DEMO_TASKS[autoIndex % DEMO_TASKS.length]
  autoIndex++
  autoProgress.value = ((autoIndex - 1) % DEMO_TASKS.length) / DEMO_TASKS.length * 100
  await execCommand(task)
  if (!autoRunning.value) return
  // countdown
  autoCountdown.value = INTERVAL
  countdownTimer = setInterval(() => {
    autoCountdown.value--
    if (autoCountdown.value <= 0) clearInterval(countdownTimer)
  }, 1000)
  autoTimer = setTimeout(() => {
    clearInterval(countdownTimer)
    runNextAuto()
  }, INTERVAL * 1000)
}

function stopAutoDemo() {
  autoRunning.value = false
  clearTimeout(autoTimer)
  clearInterval(countdownTimer)
  autoCountdown.value = 0
}

onUnmounted(() => {
  clearTimeout(autoTimer)
  clearInterval(countdownTimer)
})

function getToolName(t: string) {
  return t.split(':')[0]
}
</script>

<template>
  <div style="padding: 24px; max-width: 960px; margin: 0 auto;">
    <NSpace align="center" justify="space-between" style="margin-bottom: 20px;">
      <NSpace align="center">
        <NIcon size="22" color="#18a058"><TerminalOutline /></NIcon>
        <NText style="font-size: 20px; font-weight: 700;">遙控 Hermes</NText>
        <NTag type="success" size="small">● 已連線</NTag>
      </NSpace>
      <NSpace>
        <NButton
          v-if="!autoRunning"
          type="warning"
          @click="startAutoDemo"
          :disabled="loading"
        >
          <template #icon><NIcon><PlayOutline /></NIcon></template>
          Auto Demo
        </NButton>
        <NButton v-else type="error" @click="stopAutoDemo">
          <template #icon><NIcon><StopOutline /></NIcon></template>
          停止 Demo
        </NButton>
      </NSpace>
    </NSpace>

    <NCard v-if="autoRunning" style="margin-bottom: 16px; background: #1a1a2e;" :bordered="true">
      <NSpace vertical :size="8">
        <NSpace justify="space-between">
          <NText style="color: #f0a500; font-weight: 600;">🤖 Auto Demo 執行中</NText>
          <NText depth="3" style="font-size: 13px;">
            {{ loading ? 'Hermes 執行中...' : `下一輪：${autoCountdown}s` }}
          </NText>
        </NSpace>
        <NProgress
          type="line"
          :percentage="autoProgress"
          :show-indicator="false"
          color="#18a058"
          rail-color="#333"
        />
        <NSpace :size="6">
          <NTag v-for="(t, i) in DEMO_TASKS" :key="i"
            :type="(autoIndex - 1) % DEMO_TASKS.length === i ? 'success' : 'default'"
            size="small"
          >{{ i + 1 }}</NTag>
        </NSpace>
      </NSpace>
    </NCard>

    <NCard v-if="!autoRunning" style="margin-bottom: 20px;">
      <NSpace vertical :size="10">
        <NText depth="3" style="font-size: 13px;">輸入自然語言指令，Hermes 將自動選擇工具執行並回傳結果</NText>
        <NInput
          v-model:value="message"
          type="textarea"
          placeholder="例如：請用 terminal 查詢系統負載、記憶體狀況，並整理成報告"
          :autosize="{ minRows: 3, maxRows: 6 }"
          :disabled="loading"
          @keydown.ctrl.enter="execCommand()"
        />
        <NSpace justify="space-between" align="center">
          <NText depth="3" style="font-size: 12px;">Ctrl+Enter 送出</NText>
          <NButton type="primary" :loading="loading" @click="execCommand()" size="medium">
            <template #icon><NIcon><SendOutline /></NIcon></template>
            執行
          </NButton>
        </NSpace>
      </NSpace>
    </NCard>

    <NAlert v-if="error" type="error" style="margin-bottom: 16px;" closable @close="error=''">{{ error }}</NAlert>

    <NEmpty v-if="!loading && history.length === 0" description="尚無執行紀錄" style="padding: 60px 0;" />

    <NSpin :show="loading && history.length === 0">
      <NSpace vertical :size="16">
        <NCard v-for="item in history" :key="item.id" :bordered="true">
          <template #header>
            <NSpace align="center" :size="8">
              <NIcon size="14" color="#666"><TerminalOutline /></NIcon>
              <NText style="font-size: 13px; font-weight: 600;">{{ item.command }}</NText>
            </NSpace>
          </template>
          <template #header-extra>
            <NSpace align="center" :size="8">
              <NIcon size="12"><TimeOutline /></NIcon>
              <NText depth="3" style="font-size: 12px;">{{ item.timestamp }} · {{ item.elapsed }}s</NText>
            </NSpace>
          </template>
          <NSpace vertical :size="10">
            <NSpace v-if="item.tool_calls.length" :size="6">
              <NTag
                v-for="(t, i) in [...new Set(item.tool_calls.map(getToolName))]"
                :key="i" type="info" size="small" round
              >⚙ {{ t }}</NTag>
            </NSpace>
            <NDivider v-if="item.tool_calls.length" style="margin: 4px 0;" />
            <div v-html="renderSimpleMarkdown(item.text)" style="font-size: 14px; line-height: 1.8;" />
          </NSpace>
        </NCard>
      </NSpace>
    </NSpin>
  </div>
</template>
