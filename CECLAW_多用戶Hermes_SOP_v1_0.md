# CECLAW 多用戶 Hermes 部署 SOP v1.0
**建立日期：2026-04-10**
**執行時機：B70 到位 + Hermes v0.8.0 升級完成後**

---

## 架構概念

```
OpenClaw（公司層，單一實例，全員共用）
    ↕ shared_bridge（每員工獨立）
Hermes Profile（員工層，每人一個，完全隔離）
    ├── alice  → vault/memory/sessions 獨立
    ├── bob    → vault/memory/sessions 獨立
    └── carol  → vault/memory/sessions 獨立
```

**隔離保證：**
- 員工 A 的 vault 永不流入員工 B
- 公司知識（OpenClaw RAG）全員共用
- shared_bridge 每員工獨立橋接

---

## 前置條件

- [ ] Hermes v0.8.0 已升級（P3 hook 移植完成）
- [ ] B70 vLLM 推理層穩定
- [ ] OpenShell sandbox template 建立完成
- [ ] Admin :3005 基礎運作正常

---

## Step 1：建立員工 Profile

```bash
# 進入 Hermes 環境
cd ~/hermes-agent-fork
source .venv/bin/activate

# 建立員工 profile
hermes profile create alice
hermes profile create bob
hermes profile create carol

# 確認 profile 列表
hermes profile list
```

預期輸出：
```
Profiles:
  default (active)
  alice
  bob
  carol
```

每個 profile 路徑：`~/.hermes/profiles/{name}/`

---

## Step 2：初始化各 Profile 的 Vault

```bash
for EMPLOYEE in alice bob carol; do
  VAULT_DIR=~/.hermes/profiles/${EMPLOYEE}/vault
  mkdir -p ${VAULT_DIR}/daily

  cat > ${VAULT_DIR}/working-context.md << EOF
# Working Context - ${EMPLOYEE}
建立日期：$(date +%Y-%m-%d)
目前任務：無
進度：無
下一步：無
EOF

  cat > ${VAULT_DIR}/project-state.md << EOF
# Project State - ${EMPLOYEE}
建立日期：$(date +%Y-%m-%d)
EOF

  cat > ${VAULT_DIR}/decisions-log.md << EOF
# Decisions Log - ${EMPLOYEE}
建立日期：$(date +%Y-%m-%d)
EOF

  echo "✅ ${EMPLOYEE} vault 初始化完成"
done
```

---

## Step 3：設定各 Profile 連接 CECLAW Router

每個 profile 需要獨立的 config.yaml：

```bash
for EMPLOYEE in alice bob carol; do
  CONFIG_DIR=~/.hermes/profiles/${EMPLOYEE}
  mkdir -p ${CONFIG_DIR}

  cat > ${CONFIG_DIR}/config.yaml << EOF
model:
  provider: custom
  default: ceclaw
  base_url: http://localhost:8000/v1
  api_key: 97ad676b74d0baf2ce887a64bdc70849e96b8c977e4ad759
web:
  backend: firecrawl
platform_toolsets:
  webchat:
    - web
    - terminal
    - file
    - memory
    - session_search
EOF

  cat > ${CONFIG_DIR}/.env << EOF
FIRECRAWL_API_URL=http://localhost:2337
HERMES_PROFILE=${EMPLOYEE}
EOF

  echo "✅ ${EMPLOYEE} config 設定完成"
done
```

---

## Step 4：啟動各 Profile 的 Hermes Gateway

每個員工需要獨立的 port：

| 員工 | Hermes webapi port | Workspace port |
|------|-------------------|----------------|
| alice | 8643 | 3001 |
| bob | 8644 | 3002 |
| carol | 8645 | 3003 |

```bash
# 啟動 alice
hermes -p alice --gateway --port 8643 &

# 啟動 bob
hermes -p bob --gateway --port 8644 &

# 啟動 carol
hermes -p carol --gateway --port 8645 &
```

或寫進 start-hermes-multi.sh：

```bash
cat > ~/start-hermes-multi.sh << 'EOF'
#!/bin/bash
cd ~/hermes-agent-fork
source .venv/bin/activate

EMPLOYEES=("alice" "bob" "carol")
PORTS=(8643 8644 8645)

for i in "${!EMPLOYEES[@]}"; do
  EMPLOYEE=${EMPLOYEES[$i]}
  PORT=${PORTS[$i]}
  hermes -p ${EMPLOYEE} --gateway --port ${PORT} &
  echo "✅ ${EMPLOYEE} 啟動於 :${PORT}"
done

echo "全部員工 Hermes 啟動完成"
EOF
chmod +x ~/start-hermes-multi.sh
```

---

## Step 5：設定各 Profile 的 shared_bridge

每個員工需要獨立的 bridge 目錄：

```bash
for EMPLOYEE in alice bob carol; do
  mkdir -p ~/.ceclaw/knowledge/bridge/${EMPLOYEE}/h2o
  mkdir -p ~/.ceclaw/knowledge/bridge/${EMPLOYEE}/o2h
  echo "✅ ${EMPLOYEE} bridge 目錄建立"
done
```

修改 P3 hook，讓每個 profile 寫入各自的 bridge：

```python
# gateway/platforms/api_server.py
# P3 hook 修改：從環境變數讀取 profile
import os
EMPLOYEE = os.environ.get('HERMES_PROFILE', 'default')
BRIDGE_PATH = os.path.expanduser(
    f'~/.ceclaw/knowledge/bridge/{EMPLOYEE}/h2o'
)
```

---

## Step 6：更新 proxy.py Router 掃描多 Bridge

```python
# proxy.py 新增：掃描所有員工的 bridge
import glob

def scan_all_bridges():
    pattern = os.path.expanduser(
        '~/.ceclaw/knowledge/bridge/*/o2h/*.json'
    )
    return glob.glob(pattern)
```

---

## Step 7：健康檢查

```bash
# 檢查所有 profile gateway 狀態
for PORT in 8643 8644 8645; do
  STATUS=$(curl -s http://localhost:${PORT}/health | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'))")
  echo "Port ${PORT}: ${STATUS}"
done
```

預期輸出：
```
Port 8643: ok
Port 8644: ok
Port 8645: ok
```

---

## Step 8：Admin :3005 員工管理面板（待實作）

B70 後擴充 Admin UI，需要新增：

| 功能 | 說明 |
|------|------|
| 員工列表 | 顯示所有 profile + 在線狀態 |
| 新增員工 | `hermes profile create {name}` |
| 查看 vault | 讀取 working-context.md |
| 重啟 gateway | pm2 restart 對應 process |
| 查看 bridge 狀態 | 顯示最新 h2o/o2h 檔案 |

---

## 回滾方式

恢復單一 Hermes 實例：

```bash
pkill -f "hermes -p"
bash ~/start-hermes.sh  # 原始單一實例
```

---

## 已知限制（B70 後解決）

| 問題 | 說明 | 解決時機 |
|------|------|---------|
| 手動啟動 | 需要 start-hermes-multi.sh | B70 後改 systemd |
| Admin UI 無管理面板 | 只能 CLI 操作 | B70 後實作 |
| shared_bridge 點對點 | 需改 proxy.py | 本 SOP Step 6 |
| port 衝突風險 | 多 profile 需多 port | 固定 port 分配表 |

---

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| v1.0 | 2026-04-10 | 初版 |
