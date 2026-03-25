# CECLAW 軟工交接文件 v5.0
**日期：2026-03-26**
**總工：Claude AI（前任）**
**軟工：Claude AI（接任）**
**用戶：Kent（ColdElectric 總工程師）**

---

## 一、專案背景

CECLAW 是 ColdElectric 的企業 AI 助手系統，部署在本地 LAN 環境。核心架構：

```
Sandbox (K3s container)
  └─ OpenClaw gateway (ws://127.0.0.1:18789)
       └─ CECLAW Router (pop-os:8000)
            ├─ ollama-fast (pop-os:11434) ← minimax 模型
            ├─ gb10-llama (192.168.1.91:8001) ← 備援
            └─ proxy.py ← inject CECLAW 身份 + 日期幻覺禁令
```

**核心功能：**
- 企業 AI 助手，身份：「我是 CECLAW 企業 AI 助手」
- web_fetch 外網抓取（走 K3s proxy 10.200.0.1:3128）
- 多 sandbox 支援（ceclaw-agent / ceclaw-agent-v2）

---

## 二、系統狀態（2026-03-26 01:00 CST）

### ✅ 已完成

| 項目 | 狀態 | Commit |
|------|------|--------|
| Router v0.1.0 運行 | ✅ | - |
| proxy.py 日期幻覺禁令 | ✅ | 48258cd |
| router/main.py /v1/fetch endpoint | ✅ | 0ef2dfe |
| tcp_mux.py（已建但已回滾）| ⚠️ 回滾 | - |
| sandbox-restore.sh v3.4 | ✅ | 81a14ce |
| sandbox-restore hostname 變數修正 | ✅ | 6eec5d0 |
| ceclaw-start.sh | ✅ | 已部署兩個 sandbox |
| ceclaw-agent 修復完成 | ✅ | - |
| ceclaw-agent-v2 修復完成 | ✅ | - |
| workspace 備份到 ~/ceclaw/config/ | ✅ | 81a14ce |
| 七層健康檢查（sandbox 內跑）| ✅ | 81a14ce |

### ❌ 未完成 / 已知問題

| 項目 | 狀態 | 說明 |
|------|------|------|
| web_fetch 模型不主動呼叫 | ❌ P1 | ministral-3 tool use 能力弱 |
| L4/L5 健康檢查 403 假陰性 | ⚠️ | 從 sandbox python3 連 Router 被 K3s proxy 擋，非真實失敗 |
| searxng plugin | ❌ 暫停 | openclaw 2026.3.11 坑#77 extensions path bug |
| TOOLS.md 未更新 web_fetch 指示 | ❌ | 模型不知道怎麼主動用 web_fetch |
| ceclaw-agent sandbox TOOLS.md | ⚠️ | 基本預設值，未針對 CECLAW 優化 |

---

## 三、重要檔案路徑

### pop-os（192.168.1.x）

```
~/ceclaw/
├── sandbox-restore.sh          # v3.4 主修復腳本
├── router/
│   ├── main.py                 # Router 主程式（已回滾，無 tcp_mux）
│   ├── main.py.bak             # 回滾備份
│   ├── proxy.py                # System prompt inject + 日期幻覺禁令
│   └── tcp_mux.py              # 已建但未啟用
├── config/
│   ├── ceclaw-policy.yaml      # OpenShell network policy（外網 TLD 清單）
│   ├── SOUL.md                 # Sandbox workspace 備份
│   ├── TOOLS.md                # Sandbox workspace 備份
│   ├── AGENTS.md               # Sandbox workspace 備份
│   ├── USER.md                 # Sandbox workspace 備份
│   └── HEARTBEAT.md            # Sandbox workspace 備份
├── CECLAW_交接文件.md
├── CECLAW_EasySetup.md
├── CECLAW_重灌SOP.md
└── CECLAW_規格規劃說明書.md

~/.ceclaw/
└── router.log                  # Router 運行 log（debug 必看）
```

### Sandbox（ceclaw-agent / ceclaw-agent-v2）

```
/sandbox/.openclaw/
├── openclaw.json               # 核心設定
├── extensions/
│   └── ceclaw/                 # CECLAW plugin（身份注入）
└── workspace/
    ├── SOUL.md                 # AI 人格定義
    ├── TOOLS.md                # 工具使用說明（需更新）
    ├── AGENTS.md               # 工作流程說明
    ├── USER.md                 # 用戶資訊
    └── HEARTBEAT.md            # 心跳設定
~/.bashrc                       # proxy 設定在此
~/ceclaw-start.sh               # 乾淨啟動腳本
```

---

## 四、關鍵設定值

### Router (pop-os:8000)

```python
# proxy.py 關鍵 system prompt 注入
CECLAW_SYSTEM_PROMPT = """
你是 CECLAW 企業 AI 助手，由 ColdElectric 提供。
嚴禁提及：Qwen、qwen3、qwen2.5、通義千問...
你不知道今天的日期和時間...
"""
```

### Sandbox proxy（.bashrc）

```bash
# 關鍵：http+https 都要設，host.openshell.internal 不加 no_proxy
export http_proxy=http://10.200.0.1:3128
export https_proxy=http://10.200.0.1:3128
export HTTP_PROXY=http://10.200.0.1:3128
export HTTPS_PROXY=http://10.200.0.1:3128
export no_proxy="127.0.0.1,localhost"
export NO_PROXY="127.0.0.1,localhost"
```

### openclaw.json 關鍵欄位

```json
{
  "models": {
    "providers": {
      "local": {
        "baseUrl": "http://host.openshell.internal:8000/v1",
        "apiKey": "ceclaw-local-key",
        "api": "openai-completions"  // 坑#69！缺少會 timeout
      }
    }
  },
  "tools": {
    "web": {
      "search": {"enabled": false},
      "fetch": {"enabled": true}
    }
  }
}
```

---

## 五、Sandbox 清單

| Sandbox | ID | 狀態 |
|---------|-----|------|
| ceclaw-agent | 2e04e3db-259d-4820-ae39-af385c5d0ce1 | ✅ 正常 |
| ceclaw-agent-v2 | 35c0ad04-bb06-434c-a07d-a9a2413ee90c | ✅ 修復完成 |

---

## 六、已知坑（Pitfalls）

| 坑# | 問題 | 解法 |
|-----|------|------|
| #69 | openclaw.json 缺 `api: openai-completions` → LLM timeout | 必須加此欄位 |
| #75 | sandbox policy 動態規則只記錄 curl，不記 node | node 需要手動 approve |
| #76 | v2 sandbox Router 連線問題（K3s CNI 層攔截 urllib）| 用 gateway WebSocket，不用直連 |
| #77 | openclaw 2026.3.11 extensions path bug（dist/index.js escapes package directory）| 移除 searxng-search 目錄 |
| #78 | http_proxy 若包含 host.openshell.internal → gateway LLM timeout | no_proxy 不加此 host |
| #79 | gateway 啟動時繼承舊 shell 的空 proxy → timeout | 必須 source .bashrc 後才啟動 gateway |
| #80 | SSH known_hosts 衝突（sandbox 重建後 host key 換）| UserKnownHostsFile=/dev/null |
| #81 | bash script 裡 `tui` alias 不可用 | 改用 `openclaw tui --session fresh-$(date +%s)` |
| #82 | `scp -o "$SSH_OPTS"` 整個變數當一個 -o 參數 → 語法錯誤 | 展開成多個 `-o` 參數 |

---

## 七、TODO List（優先順序）

### P0 - 立刻處理

- [ ] **TOOLS.md 更新**：加入 web_fetch 強制指示，讓模型知道必須主動呼叫
  - 路徑：`~/ceclaw/config/TOOLS.md`
  - 修改後重新 restore 兩個 sandbox
  - 測試：TUI 問天氣 → 模型主動呼叫 web_fetch

### P1 - 本週

- [ ] **L4/L5 健康檢查修正**：
  - 目前從 sandbox python3 連 Router 會 403（K3s proxy 擋 urllib）
  - 解法：L4/L5 改用 `curl --noproxy '*'` 或接受此限制，標記為「已知假陰性」
  - 或 v3.5 只用 curl 做 L4/L5

- [ ] **web_fetch 新 host approve 流程自動化**：
  - 目前每個新 domain 需在 openshell term 手動 approve
  - 考慮把常用 domain 加進 ceclaw-policy.yaml 白名單
  - 常用：wttr.in, openweathermap.org, finance.yahoo.com

- [ ] **ceclaw-agent TOOLS.md 優化**：
  - 加入 web_fetch 使用範例
  - 加入 Router 連線說明
  - 加入常見問題排查

### P2 - 下週

- [ ] **searxng plugin 重新啟用**：等 openclaw 升級修復坑#77
- [ ] **POC 多人測試**：Step 2 測試 2 人同時使用
- [ ] **CECLaw policy.yaml 完善**：引導客戶選 skill 白名單，one-click 生成

---

## 八、Debug 流程

### TUI 無法回應 / timeout

```bash
# Step 1: 確認 Router 正常
curl -s http://localhost:8000/ceclaw/status  # pop-os 跑

# Step 2: 確認 gateway 有收到請求
grep "inject_system_prompt" ~/.ceclaw/router.log | tail -3

# Step 3: 確認 Router 有轉發成功
grep "ollama-fast\|gb10-llama\|200\|timeout" ~/.ceclaw/router.log | tail -5

# Step 4: sandbox 內確認 proxy
cat /proc/$(pgrep openclaw-gateway)/environ | tr '\0' '\n' | grep proxy
```

### web_fetch 失敗

```bash
# sandbox 內確認 proxy
echo $http_proxy $https_proxy

# 手動測試
curl -x http://10.200.0.1:3128 https://wttr.in/taipei?format=3

# 如果 403 → 需要在 openshell term approve
# 如果 tunnel failed → K3s policy 未 approve 此 domain
```

### Gateway 起不來（port occupied）

```bash
pkill -9 -f 'openclaw' 2>/dev/null
sleep 3
source ~/.bashrc
openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
sleep 10
tail -5 /tmp/openclaw-gateway.log
```

### Restore 腳本 SSH 連不進去

```bash
# 清除 known_hosts
ssh-keygen -f "/home/zoe_ai/.ssh/known_hosts" -R "ceclaw-agent"
ssh-keygen -f "/home/zoe_ai/.ssh/known_hosts" -R "ceclaw-agent-v2"

# 確認 openshell ssh-proxy 在跑
ps aux | grep "openshell ssh-proxy" | grep -v grep
```

---

## 九、常用指令速查

### pop-os

```bash
# Router 狀態
curl -s http://localhost:8000/ceclaw/status

# Router log
tail -20 ~/.ceclaw/router.log

# Restart Router
sudo systemctl restart ceclaw-router

# Restore ceclaw-agent
bash ~/ceclaw/sandbox-restore.sh

# Restore ceclaw-agent-v2
SANDBOX_ID=35c0ad04-bb06-434c-a07d-a9a2413ee90c \
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep "35c0ad04" | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}') \
bash ~/ceclaw/sandbox-restore.sh

# 備份 workspace
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep "2e04e3db" | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
for f in SOUL.md TOOLS.md AGENTS.md USER.md HEARTBEAT.md; do
  scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o "ProxyCommand=/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id 2e04e3db-259d-4820-ae39-af385c5d0ce1 --token $TOKEN --gateway-name openshell" \
    sandbox@ceclaw-agent:/sandbox/.openclaw/workspace/$f ~/ceclaw/config/$f
done
```

### Sandbox 內

```bash
# 乾淨啟動
bash ~/ceclaw-start.sh

# 手動測試 Router 連線
curl --noproxy '*' -s http://host.openshell.internal:8000/ceclaw/status

# 手動測試 web_fetch
curl -x http://10.200.0.1:3128 https://wttr.in/taipei?format=3

# 查看 gateway log
tail -20 /tmp/openclaw-gateway.log
cat /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -20
```

---

## 十、Git 歷史（本對話）

```
6eec5d0  fix: sandbox-restore hostname 用 SANDBOX_NAME 變數
81a14ce  feat: sandbox-restore v3.4 - workspace 同步，ceclaw-start 部署，sandbox 內健康檢查
a225015  feat: sandbox-restore v3.3 - 七層健康檢查 + 自動修復
4ac166a  feat: sandbox-restore v3.2 - 修正 proxy，加環境自我檢查
96af449  fix: sandbox-restore v3.1 加 UserKnownHostsFile=/dev/null
d443c13  feat: sandbox-restore v3.0 - 修正 proxy/searxng bug，網路全開放
0ef2dfe  feat: router/main.py 加 /v1/fetch proxy endpoint
48258cd  fix: proxy.py 日期幻覺禁令
e054a22  docs: 四份文件更新至最新狀態
```

---

## 十一、下個軟工的第一步

1. 閱讀本文件
2. 確認 Router 正常：`curl -s http://localhost:8000/ceclaw/status`
3. 確認 ceclaw-agent 正常：`openshell sandbox connect ceclaw-agent` → `bash ~/ceclaw-start.sh` → 問「你是誰」
4. 處理 **P0 TOOLS.md** 問題（模型不主動呼叫 web_fetch）
5. 遇到問題先看 `~/.ceclaw/router.log`

---

## 十二、網路架構說明

```
Sandbox (10.200.0.x)
  │
  ├─ http/https → K3s proxy (10.200.0.1:3128) → 外網
  │   └─ 注意：node binary 需要 openshell term approve 每個新 domain
  │
  └─ host.openshell.internal:8000 → K3s proxy → pop-os:8000 (Router)
      └─ gateway WebSocket 走此路徑
      └─ 不要加進 no_proxy！否則 LLM timeout

pop-os (172.17.0.1 / 192.168.1.x)
  ├─ Router port 8000 (uvicorn)
  ├─ ollama port 11434
  └─ GB10 192.168.1.91:8001
```

---

*本文件由 Claude AI 總工生成，2026-03-26 01:xx CST*
*下一個軟工：請直接開始，不要重複已完成項目*
