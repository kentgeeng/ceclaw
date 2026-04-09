#!/usr/bin/env python3
"""CECLAW MyWorld Patch v3 - 合併所有改動"""
import sys

TARGET = '/home/zoe_ai/openclaw-admin/src/views/myworld/MyWorldPage.vue'

with open(TARGET, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)

errors = []

def replace_once(old, new, label):
    global content
    if old not in content:
        errors.append(f"❌ {label}: 找不到目標字串")
        return False
    content = content.replace(old, new, 1)
    print(f"✅ {label}")
    return True

# ── 1. 縮小場景 ──────────────────────────────────────────────────────────
replace_once('const sceneWidth = ref(1800)', 'const sceneWidth = ref(1100)', '縮小場景寬')
replace_once('const sceneHeight = ref(1250)', 'const sceneHeight = ref(780)', '縮小場景高')

# ── 2. 替換房間定義（用行號定位）────────────────────────────────────────
# 找 rooms computed 開始到 walls computed 開始之間
rooms_start = content.find('const rooms = computed<Room[]>(() => [')
walls_start = content.find('const walls = computed<Wall[]>(() => {')

if rooms_start == -1 or walls_start == -1:
    print("❌ 找不到房間或牆壁定義"); sys.exit(1)

OLD_ROOMS_BLOCK = content[rooms_start:walls_start]

NEW_ROOMS_BLOCK = """const rooms = computed<Room[]>(() => [
  { id: 'reception', name: t('myworld.areas.reception'), type: 'reception', x: 50, y: 30, width: 1000, height: 180, hasWalls: false, doors: [] },
  { id: 'office-1', name: t('myworld.areas.office1'), type: 'office', x: 50, y: 255, width: 285, height: 215, hasWalls: true, doors: [{ position: 'top', offset: 142, width: 65 }, { position: 'right', offset: 107, width: 65 }], deskCount: 6 },
  { id: 'office-2', name: t('myworld.areas.office2'), type: 'office', x: 385, y: 255, width: 285, height: 215, hasWalls: true, doors: [{ position: 'top', offset: 142, width: 65 }, { position: 'left', offset: 107, width: 65 }, { position: 'right', offset: 107, width: 65 }], deskCount: 6 },
  { id: 'office-3', name: t('myworld.areas.office3'), type: 'office', x: 720, y: 255, width: 285, height: 215, hasWalls: true, doors: [{ position: 'top', offset: 142, width: 65 }, { position: 'left', offset: 107, width: 65 }], deskCount: 6 },
  { id: 'meeting-large', name: t('myworld.areas.meetingRoom'), type: 'meeting-large', x: 50, y: 520, width: 310, height: 215, hasWalls: true, doors: [{ position: 'top', offset: 155, width: 65 }, { position: 'right', offset: 107, width: 65 }] },
  { id: 'pantry', name: t('myworld.areas.pantry'), type: 'pantry', x: 420, y: 520, width: 220, height: 215, hasWalls: false, doors: [] },
  { id: 'lounge', name: t('myworld.areas.lounge'), type: 'lounge', x: 710, y: 520, width: 295, height: 215, hasWalls: false, doors: [] },
])
"""

content = content[:rooms_start] + NEW_ROOMS_BLOCK + content[walls_start:]
print("✅ 替換房間（7個）")

# ── 3. 暖色調地板 ────────────────────────────────────────────────────────
replace_once(
    'background: linear-gradient(180deg, #374151 0%, #4b5563 100%);',
    'background: linear-gradient(180deg, #2d1a08 0%, #3a2210 100%);',
    '暖色調地板底色'
)
replace_once(
    '  background-image:\n    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px),\n    linear-gradient(0deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);\n  background-size: 50px 50px;',
    '  background-image:\n    linear-gradient(90deg, rgba(255, 200, 100, 0.07) 1px, transparent 1px),\n    linear-gradient(0deg, rgba(255, 200, 100, 0.07) 1px, transparent 1px);\n  background-size: 32px 32px;',
    '地板格線暖色'
)

# ── 4. 房間地板配色 ──────────────────────────────────────────────────────
replace_once(
    '.room-office .room-floor,\n.room-open-desk .room-floor {\n  background: linear-gradient(135deg, rgba(59, 130, 246, 0.06) 0%, rgba(59, 130, 246, 0.02) 100%);\n}',
    '.room-office .room-floor,\n.room-open-desk .room-floor {\n  background: linear-gradient(135deg, rgba(180, 95, 15, 0.3) 0%, rgba(140, 65, 5, 0.2) 100%);\n}',
    '辦公室橙色地板'
)
replace_once(
    '.room-meeting-small .room-floor,\n.room-meeting-large .room-floor {\n  background: linear-gradient(135deg, rgba(168, 85, 247, 0.06) 0%, rgba(168, 85, 247, 0.02) 100%);\n}',
    '.room-meeting-small .room-floor,\n.room-meeting-large .room-floor {\n  background: linear-gradient(135deg, rgba(110, 40, 200, 0.3) 0%, rgba(80, 20, 160, 0.2) 100%);\n}',
    '會議室紫色地板'
)
replace_once(
    '.room-lounge .room-floor {\n  background: linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, rgba(16, 185, 129, 0.02) 100%);\n}',
    '.room-lounge .room-floor {\n  background: linear-gradient(135deg, rgba(15, 130, 160, 0.35) 0%, rgba(8, 90, 115, 0.25) 100%);\n}',
    '休息室藍色地板'
)

# ── 5. 放大角色 ──────────────────────────────────────────────────────────
replace_once(
    '.character-head {\n  position: relative;\n  width: 14px;\n  height: 16px;',
    '.character-head {\n  position: relative;\n  width: 22px;\n  height: 24px;',
    '角色頭部放大'
)
replace_once(
    '.character-torso {\n  position: relative;\n  width: 18px;\n  height: 16px;\n  background: linear-gradient(180deg, var(--primary) 0%, var(--secondary) 100%);\n  border-radius: 5px 5px 2px 2px;\n  margin-top: -1px;\n  z-index: 2;\n}',
    '.character-torso {\n  position: relative;\n  width: 26px;\n  height: 22px;\n  background: linear-gradient(180deg, var(--primary) 0%, var(--secondary) 100%);\n  border-radius: 6px 6px 3px 3px;\n  margin-top: -1px;\n  z-index: 2;\n}',
    '角色身體放大'
)
replace_once(
    '.leg {\n  width: 6px;\n  height: 14px;\n  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);\n  border-radius: 0 0 2px 2px;\n}',
    '.leg {\n  width: 9px;\n  height: 18px;\n  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);\n  border-radius: 0 0 3px 3px;\n}',
    '角色腿部放大'
)
replace_once(
    '.arm {\n  position: absolute;\n  top: 2px;\n  width: 4px;\n  height: 12px;',
    '.arm {\n  position: absolute;\n  top: 2px;\n  width: 6px;\n  height: 16px;',
    '角色手臂放大'
)

# ── 6. 加狀態 ref（在 currentTime 後面）──────────────────────────────────
replace_once(
    'const currentTime = ref(Date.now())',
    '''const currentTime = ref(Date.now())

// CECLAW 系統狀態
const ceclawStatus = ref({
  qdrant: { healthy: false, count: 0 },
  hermes: { healthy: false },
  gateway: { healthy: false },
  checkedAt: '',
})''',
    '加狀態 ref'
)

# ── 7. 加 checkCeclawStatus 函數（在 onMounted 前）───────────────────────
replace_once(
    'onMounted(async () => {',
    '''async function checkCeclawStatus() {
  try {
    const r = await fetch('http://192.168.1.91:6333/collections', { signal: AbortSignal.timeout(3000) })
    if (r.ok) {
      const d = await r.json()
      ceclawStatus.value.qdrant = { healthy: true, count: d.result?.collections?.length ?? 0 }
    } else { ceclawStatus.value.qdrant = { healthy: false, count: 0 } }
  } catch { ceclawStatus.value.qdrant = { healthy: false, count: 0 } }
  try {
    const r = await fetch('http://localhost:8642/health', { signal: AbortSignal.timeout(3000) })
    ceclawStatus.value.hermes = { healthy: r.ok }
  } catch { ceclawStatus.value.hermes = { healthy: false } }
  try {
    const r = await fetch('http://localhost:18789/api/v1/health', { signal: AbortSignal.timeout(3000) })
    ceclawStatus.value.gateway = { healthy: r.ok }
  } catch { ceclawStatus.value.gateway = { healthy: false } }
  const now = new Date()
  ceclawStatus.value.checkedAt = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`
}

onMounted(async () => {''',
    '加 checkCeclawStatus 函數'
)

# ── 8. 在 onMounted 裡加輪詢 ─────────────────────────────────────────────
replace_once(
    '  await officeStore.loadOfficeData()\n  await sessionStore.fetchSessions()',
    '''  await officeStore.loadOfficeData()
  await sessionStore.fetchSessions()
  await checkCeclawStatus()
  const statusInterval = setInterval(checkCeclawStatus, 30000)
  eventCleanups.push(() => clearInterval(statusInterval))''',
    '加狀態輪詢'
)

# ── 9. 加狀態面板 HTML（在 entrance-marker 前）──────────────────────────
replace_once(
    '        <div class="entrance-marker">',
    '''        <!-- CECLAW 狀態面板 -->
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

        <div class="entrance-marker">''',
    '加狀態面板 HTML'
)

# ── 10. 加 CSS ───────────────────────────────────────────────────────────
replace_once(
    '</style>',
    '''
/* CECLAW 狀態面板 */
.ceclaw-status-panel {
  position: absolute;
  top: 40px;
  right: 40px;
  background: rgba(8, 14, 30, 0.95);
  border: 1px solid rgba(99, 102, 241, 0.5);
  border-radius: 14px;
  padding: 14px 18px;
  z-index: 50;
  min-width: 175px;
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(99,102,241,0.1);
}
.status-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  color: rgba(129, 140, 248, 0.95);
  margin-bottom: 10px;
  text-transform: uppercase;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.green {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
  animation: status-pulse 2s infinite;
}
.status-dot.red {
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
}
@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.status-label {
  font-size: 12px;
  color: #cbd5e1;
  font-weight: 600;
  min-width: 58px;
}
.status-val {
  font-size: 12px;
  color: #f1f5f9;
  font-weight: 700;
  margin-left: auto;
}
.status-time {
  font-size: 9px;
  color: #475569;
  text-align: right;
  margin-top: 6px;
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 6px;
}
</style>''',
    '加 CSS'
)

# ── 結果 ─────────────────────────────────────────────────────────────────
if errors:
    print("\n⚠️  有些步驟失敗：")
    for e in errors:
        print(" ", e)
    print("\n請貼錯誤給軟工檢查。")
else:
    with open(TARGET, 'w', encoding='utf-8') as f:
        f.write(content)
    print("\n🎉 全部完成！執行：")
    print("  cd ~/openclaw-admin && npm run build && pm2 restart ceclaw-admin")
