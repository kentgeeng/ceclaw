#!/usr/bin/env python3
"""
CECLAW MyWorld Patch v2
- 縮小辦公室（只留7個房間）
- 角色放大
- 暖色調地板
- 狀態面板放大
"""
import re, sys

TARGET = '/home/zoe_ai/openclaw-admin/src/views/myworld/MyWorldPage.vue'

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. 縮小場景尺寸 ──────────────────────────────────────────────────────
content = content.replace(
    'const sceneWidth = ref(1800)',
    'const sceneWidth = ref(1100)'
)
content = content.replace(
    'const sceneHeight = ref(1250)',
    'const sceneHeight = ref(800)'
)
print("✅ Step 1: 縮小場景")

# ── 2. 替換房間定義（只留7個）────────────────────────────────────────────
OLD_ROOMS_START = "const rooms = computed<Room[]>(() => ["
OLD_ROOMS_END = "])\nconst walls"

start_idx = content.find(OLD_ROOMS_START)
end_idx = content.find(OLD_ROOMS_END, start_idx)
if start_idx == -1 or end_idx == -1:
    print("❌ 找不到房間定義"); sys.exit(1)

NEW_ROOMS = """const rooms = computed<Room[]>(() => [
  // 接待區（頂部橫跨）
  { id: 'reception', name: t('myworld.areas.reception'), type: 'reception', x: 50, y: 30, width: 1000, height: 200, hasWalls: false, doors: [] },
  // 辦公室 3 個
  { id: 'office-1', name: t('myworld.areas.office1'), type: 'office', x: 50, y: 270, width: 280, height: 220, hasWalls: true, doors: [{ position: 'top', offset: 140, width: 60 }, { position: 'right', offset: 110, width: 60 }], deskCount: 6 },
  { id: 'office-2', name: t('myworld.areas.office2'), type: 'office', x: 380, y: 270, width: 280, height: 220, hasWalls: true, doors: [{ position: 'top', offset: 140, width: 60 }, { position: 'left', offset: 110, width: 60 }, { position: 'right', offset: 110, width: 60 }], deskCount: 6 },
  { id: 'office-3', name: t('myworld.areas.office3'), type: 'office', x: 710, y: 270, width: 280, height: 220, hasWalls: true, doors: [{ position: 'top', offset: 140, width: 60 }, { position: 'left', offset: 110, width: 60 }], deskCount: 6 },
  // 會議室
  { id: 'meeting-large', name: t('myworld.areas.meetingRoom'), type: 'meeting-large', x: 50, y: 540, width: 320, height: 220, hasWalls: true, doors: [{ position: 'top', offset: 160, width: 60 }, { position: 'right', offset: 110, width: 60 }] },
  // 茶水間
  { id: 'pantry', name: t('myworld.areas.pantry'), type: 'pantry', x: 430, y: 540, width: 220, height: 220, hasWalls: false, doors: [] },
  // 休息室
  { id: 'lounge', name: t('myworld.areas.lounge'), type: 'lounge', x: 720, y: 540, width: 280, height: 220, hasWalls: false, doors: [] },
])
"""

content = content[:start_idx] + NEW_ROOMS + content[end_idx + len(OLD_ROOMS_START) - len("const rooms = computed<Room[]>(() => ["):]

# fix: the end marker replacement
content = content.replace(NEW_ROOMS + content[start_idx + len(NEW_ROOMS):start_idx + len(NEW_ROOMS) + 50], NEW_ROOMS)

print("✅ Step 2: 替換房間（7個）")

# ── 3. 放大角色（調整 character body 尺寸）──────────────────────────────
# head
content = content.replace(
    '.character-head {\n  position: relative;\n  width: 14px;\n  height: 16px;',
    '.character-head {\n  position: relative;\n  width: 20px;\n  height: 22px;'
)
# torso
content = content.replace(
    '.character-torso {\n  position: relative;\n  width: 18px;\n  height: 16px;',
    '.character-torso {\n  position: relative;\n  width: 24px;\n  height: 22px;'
)
# leg
content = content.replace(
    '.leg {\n  width: 6px;\n  height: 14px;',
    '.leg {\n  width: 9px;\n  height: 18px;'
)
print("✅ Step 3: 放大角色")

# ── 4. 暖色調地板 ────────────────────────────────────────────────────────
content = content.replace(
    'background: linear-gradient(180deg, #374151 0%, #4b5563 100%);',
    'background: linear-gradient(180deg, #2d1f0e 0%, #3d2a12 100%);'
)
content = content.replace(
    '''  background-image:
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(0deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;''',
    '''  background-image:
    linear-gradient(90deg, rgba(255, 220, 150, 0.06) 1px, transparent 1px),
    linear-gradient(0deg, rgba(255, 220, 150, 0.06) 1px, transparent 1px);
  background-size: 32px 32px;'''
)
print("✅ Step 4: 暖色調地板")

# ── 5. 辦公室地板改橙色 ─────────────────────────────────────────────────
content = content.replace(
    '.room-office .room-floor,\n.room-open-desk .room-floor {\n  background: linear-gradient(135deg, rgba(59, 130, 246, 0.06) 0%, rgba(59, 130, 246, 0.02) 100%);\n}',
    '.room-office .room-floor,\n.room-open-desk .room-floor {\n  background: linear-gradient(135deg, rgba(180, 100, 20, 0.25) 0%, rgba(140, 70, 10, 0.15) 100%);\n}'
)
# 會議室改紫
content = content.replace(
    '.room-meeting-small .room-floor,\n.room-meeting-large .room-floor {\n  background: linear-gradient(135deg, rgba(168, 85, 247, 0.06) 0%, rgba(168, 85, 247, 0.02) 100%);\n}',
    '.room-meeting-small .room-floor,\n.room-meeting-large .room-floor {\n  background: linear-gradient(135deg, rgba(120, 50, 200, 0.25) 0%, rgba(90, 30, 160, 0.15) 100%);\n}'
)
# 休息室改藍綠
content = content.replace(
    '.room-lounge .room-floor {\n  background: linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, rgba(16, 185, 129, 0.02) 100%);\n}',
    '.room-lounge .room-floor {\n  background: linear-gradient(135deg, rgba(20, 140, 160, 0.3) 0%, rgba(10, 100, 120, 0.2) 100%);\n}'
)
print("✅ Step 5: 房間配色")

# ── 6. 放大狀態面板 ──────────────────────────────────────────────────────
content = content.replace(
    '''.ceclaw-status-panel {
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
}''',
    '''.ceclaw-status-panel {
  position: absolute;
  top: 40px;
  right: 40px;
  background: rgba(10, 18, 38, 0.95);
  border: 1px solid rgba(99, 102, 241, 0.5);
  border-radius: 14px;
  padding: 14px 18px;
  z-index: 50;
  min-width: 180px;
  backdrop-filter: blur(16px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(99,102,241,0.1);
}'''
)
content = content.replace(
    '.status-title {\n  font-size: 8px;\n  font-weight: 700;\n  letter-spacing: 1.5px;\n  color: rgba(99, 102, 241, 0.8);\n  margin-bottom: 8px;\n  text-transform: uppercase;\n}',
    '.status-title {\n  font-size: 10px;\n  font-weight: 700;\n  letter-spacing: 2px;\n  color: rgba(129, 140, 248, 0.95);\n  margin-bottom: 10px;\n  text-transform: uppercase;\n}'
)
content = content.replace(
    '.status-dot {\n  width: 7px;\n  height: 7px;',
    '.status-dot {\n  width: 10px;\n  height: 10px;'
)
content = content.replace(
    '.status-label {\n  font-size: 10px;\n  color: #94a3b8;\n  font-weight: 500;\n  min-width: 48px;\n}',
    '.status-label {\n  font-size: 12px;\n  color: #cbd5e1;\n  font-weight: 600;\n  min-width: 60px;\n}'
)
content = content.replace(
    '.status-val {\n  font-size: 10px;\n  color: #e2e8f0;\n  font-weight: 600;\n  margin-left: auto;\n}',
    '.status-val {\n  font-size: 12px;\n  color: #f1f5f9;\n  font-weight: 700;\n  margin-left: auto;\n}'
)
content = content.replace(
    '.status-row {\n  display: flex;\n  align-items: center;\n  gap: 7px;\n  margin-bottom: 5px;\n}',
    '.status-row {\n  display: flex;\n  align-items: center;\n  gap: 10px;\n  margin-bottom: 8px;\n}'
)
print("✅ Step 6: 放大狀態面板")

# ── 寫回 ─────────────────────────────────────────────────────────────────
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n🎉 Patch v2 完成！執行：")
print("  cd ~/openclaw-admin && npm run build")
print("  pm2 restart ceclaw-admin")
