#!/usr/bin/env python3
"""
CECLAW MyWorld Patch
加入：狀態輪詢 + 右上角狀態面板 + 視覺微調
"""
import sys

TARGET = '/home/zoe_ai/openclaw-admin/src/views/myworld/MyWorldPage.vue'

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. 加狀態 ref（在 currentTime 後面）──────────────────────────────────
STATUS_REFS = """
// CECLAW 系統狀態
const ceclawStatus = ref({
  qdrant: { healthy: false, count: 0 },
  hermes: { healthy: false },
  gateway: { healthy: false },
  checkedAt: '',
})
"""
ANCHOR1 = "const currentTime = ref(Date.now())"
if ANCHOR1 not in content:
    print("❌ 找不到插入點 1，請確認版本"); sys.exit(1)
content = content.replace(ANCHOR1, ANCHOR1 + "\n" + STATUS_REFS, 1)
print("✅ Step 1: 加狀態 ref")

# ── 2. 加 checkCeclawStatus 函數（在 onMounted 前）───────────────────────
STATUS_FN = """
async function checkCeclawStatus() {
  // Qdrant
  try {
    const r = await fetch('http://192.168.1.91:6333/collections', { signal: AbortSignal.timeout(3000) })
    if (r.ok) {
      const d = await r.json()
      ceclawStatus.value.qdrant = { healthy: true, count: d.result?.collections?.length ?? 0 }
    } else {
      ceclawStatus.value.qdrant = { healthy: false, count: 0 }
    }
  } catch { ceclawStatus.value.qdrant = { healthy: false, count: 0 } }

  // Hermes
  try {
    const r = await fetch('http://localhost:8642/health', { signal: AbortSignal.timeout(3000) })
    ceclawStatus.value.hermes = { healthy: r.ok }
  } catch { ceclawStatus.value.hermes = { healthy: false } }

  // Gateway
  try {
    const r = await fetch('http://localhost:18789/api/v1/health', { signal: AbortSignal.timeout(3000) })
    ceclawStatus.value.gateway = { healthy: r.ok }
  } catch { ceclawStatus.value.gateway = { healthy: false } }

  const now = new Date()
  ceclawStatus.value.checkedAt = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`
}
"""
ANCHOR2 = "onMounted(async () => {"
if ANCHOR2 not in content:
    print("❌ 找不到插入點 2"); sys.exit(1)
content = content.replace(ANCHOR2, STATUS_FN + "\n" + ANCHOR2, 1)
print("✅ Step 2: 加 checkCeclawStatus 函數")

# ── 3. 在 onMounted 裡加輪詢（在 loadOfficeData 後）─────────────────────
POLLING = """  // CECLAW 狀態輪詢
  await checkCeclawStatus()
  const statusInterval = setInterval(checkCeclawStatus, 30000)
  eventCleanups.push(() => clearInterval(statusInterval))
"""
ANCHOR3 = "  await officeStore.loadOfficeData()"
if ANCHOR3 not in content:
    print("❌ 找不到插入點 3"); sys.exit(1)
content = content.replace(ANCHOR3, ANCHOR3 + "\n" + POLLING, 1)
print("✅ Step 3: 加輪詢")

# ── 4. 在 template 加狀態面板（在 entrance-marker 前）──────────────────
STATUS_PANEL = """        <!-- CECLAW 狀態面板 -->
        <div class="ceclaw-status-panel">
          <div class="status-title">CECLAW STATUS</div>
          <div class="status-row">
            <span class="status-dot" :class="ceclawStatus.qdrant.healthy ? 'green' : 'red'"></span>
            <span class="status-label">RAG</span>
            <span class="status-val">{{ ceclawStatus.qdrant.healthy ? ceclawStatus.qdrant.count + ' cols' : 'offline' }}</span>
          </div>
          <div class="status-row">
            <span class="status-dot" :class="ceclawStatus.hermes.healthy ? 'green' : 'red'"></span>
            <span class="status-label">Hermes</span>
            <span class="status-val">{{ ceclawStatus.hermes.healthy ? 'online' : 'offline' }}</span>
          </div>
          <div class="status-row">
            <span class="status-dot" :class="ceclawStatus.gateway.healthy ? 'green' : 'red'"></span>
            <span class="status-label">Gateway</span>
            <span class="status-val">{{ ceclawStatus.gateway.healthy ? 'online' : 'offline' }}</span>
          </div>
          <div class="status-time" v-if="ceclawStatus.checkedAt">{{ ceclawStatus.checkedAt }}</div>
        </div>
"""
ANCHOR4 = '<div class="entrance-marker">'
if ANCHOR4 not in content:
    print("❌ 找不到插入點 4"); sys.exit(1)
content = content.replace(ANCHOR4, STATUS_PANEL + "        " + ANCHOR4, 1)
print("✅ Step 4: 加狀態面板 HTML")

# ── 5. 加 CSS（在 </style> 前）──────────────────────────────────────────
STATUS_CSS = """
/* CECLAW 狀態面板 */
.ceclaw-status-panel {
  position: absolute;
  top: 40px;
  right: 40px;
  background: rgba(10, 18, 38, 0.92);
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 12px;
  padding: 10px 14px;
  z-index: 50;
  min-width: 140px;
  backdrop-filter: blur(12px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.status-title {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: rgba(99, 102, 241, 0.8);
  margin-bottom: 8px;
  text-transform: uppercase;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 5px;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.green {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
  animation: status-pulse-green 2s infinite;
}
.status-dot.red {
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
}
@keyframes status-pulse-green {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
.status-label {
  font-size: 10px;
  color: #94a3b8;
  font-weight: 500;
  min-width: 48px;
}
.status-val {
  font-size: 10px;
  color: #e2e8f0;
  font-weight: 600;
  margin-left: auto;
}
.status-time {
  font-size: 8px;
  color: #475569;
  text-align: right;
  margin-top: 6px;
  border-top: 1px solid rgba(255,255,255,0.05);
  padding-top: 5px;
}
"""
ANCHOR5 = "</style>"
if ANCHOR5 not in content:
    print("❌ 找不到 </style>"); sys.exit(1)
content = content.replace(ANCHOR5, STATUS_CSS + "\n" + ANCHOR5, 1)
print("✅ Step 5: 加 CSS")

# ── 寫回 ─────────────────────────────────────────────────────────────────
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n🎉 Patch 完成！執行：")
print("  cd ~/openclaw-admin && npm run build")
print("  pm2 restart ceclaw-admin")
