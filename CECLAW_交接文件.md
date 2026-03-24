# CECLAW 專案交接文件 v4.5
## 給下一個對話的軟工 + 總工角色說明

**總工（Kent）**：35年工程經驗，ZOE AI Digital Twin 作者，做決策、設計審核
**軟工（下個對話）**：負責實作、測試、debug，遇困難問總工
**原則**：SOP-002 — 每次動手前說意圖，等 Kent 確認；每步完成後 commit
**督察**：GLM-5 Turbo（OpenRouter）— 品質審查，$0.12/次

---

## ⚠️ 本次對話重要進展摘要（v4.4 → v4.5）

### 已完成 ✅

1. **6000 輪燒機 100%** ✅
   - Fast path 3000/3000，avg 621ms
   - Main path 3000/3000，avg 2594ms
   - SearXNG 60/60 檢查點 100%
   - 全簡體異常 1/3000（0.03%）

2. **#66 SearXNG 穩定性盤查** ✅
   - 14/14 檢查點全通，零 retry
   - 查詢詞改英文（curl URL encode 根因）

3. **openclaw 升級 2026.3.13（pop-os 側）** ✅
   - `npm install -g openclaw@2026.3.13` 在 pop-os 完成
   - pop-os: `OpenClaw 2026.3.13 (61d171a)` ✅
   - **sandbox 內仍是 2026.3.11**（base image ARM64，無法直接升級）

4. **sandbox 重建 + 網路問題全面排查** ✅（今日重大突破）
   - 發現真正根因：openclaw.json 缺少 `api: "openai-completions"` 欄位
   - 加入後 TUI 成功回應：`我是 CECLAW 企業 AI 助手`
   - 新 sandbox ID：`2e04e3db-259d-4820-ae39-af385c5d0ce1`

5. **網路層全面排查（重要發現，需寫進 SOP）**
   - gateway 重建會讓舊 sandbox 消失（K3s PVC 綁定問題）
   - openshell container 實際網段：`172.19.0.0/16`（非 `172.20.0.0/16`）
   - sandbox 內有 `ALL_PROXY` 環境變數，需用 `--noproxy "*"` 繞過
   - UFW `deny (routed)` 已改為 `allow routed`
   - INPUT chain 缺少 `172.19.0.0/16 → port 8000` 規則（已加）

### 當前狀態

| Phase | 項目 | 狀態 | Commit |
|-------|------|------|--------|
| P1 #66 | SearXNG 穩定性盤查 | ✅ 今日 | — |
| openclaw | 升級 2026.3.13（pop-os）| ✅ | — |
| **TUI 身份驗證** | `你是誰` → CECLAW 回應 | ✅ 今日 | — |
| **SearXNG TUI** | 天氣查詢 → 用 Brave 非 SearXNG | ⚠️ 未完成 | — |
| P1 #39 | Qwen2.5-72B 評估 | ⬜ | — |
| P1 #60 | fallback warning | ⬜ | — |
| P1 #61 | 台積電/NVIDIA股價漏答 | ⬜ | — |
| P1 #62 | gb10 retry 機制 | ⬜ | — |
| P6 | NemoClaw drop-in 驗證 | ⬜ | — |
| P7 | Skill 相容性測試 | ⬜ | — |
| P8 | UX 升級 | ⬜ | — |
| **#67** | **Plugin OTA + 官方SDK重寫 + ceclaw update 一鍵更新** | ⬜ 新開 | — |

---

## 🚨 最緊急待辦：SearXNG Plugin 未正確載入

### 問題描述
TUI 問「今天台北天氣」→ 回應用 Brave Search API（未設定），而非 SearXNG plugin。
SearXNG plugin 已安裝但沒有被 openclaw 正確呼叫。

### Debug 步驟

**Step 1：確認 plugin 狀態**
```bash
# sandbox 內
cat /tmp/openclaw-gateway.log | grep -i "searxng\|plugin" | tail -20
ls /sandbox/.openclaw/extensions/searxng-search/
ls /sandbox/.openclaw/extensions/searxng-search/dist/
```

**Step 2：確認 openclaw.json plugin 設定**
```bash
python3 -c "
import json
cfg = json.load(open('/sandbox/.openclaw/openclaw.json'))
print('plugins:', json.dumps(cfg.get('plugins',{}), indent=2))
print('tools:', json.dumps(cfg.get('tools',{}), indent=2))
"
```

**Step 3：確認 tools 設定**
openclaw.json 必須有：
```json
"tools": {
    "web": {
        "search": {"enabled": true},
        "fetch": {"enabled": true}
    }
}
```

**Step 4：確認 plugins.allow**
2026.3.11 有新安全要求，plugin 必須在 `plugins.allow` 白名單：
```bash
python3 -c "
import json
cfg = json.load(open('/sandbox/.openclaw/openclaw.json'))
print('allow:', cfg.get('plugins',{}).get('allow','MISSING'))
"
```

若沒有，加入：
```python
cfg["plugins"]["allow"] = ["searxng-search", "ceclaw"]
```

**Step 5：SearXNG 連通測試**
```bash
# sandbox 內，繞過 proxy
curl --noproxy "*" "http://host.openshell.internal:8000/search?q=taipei+weather&format=json" | python3 -c "import json,sys; d=json.load(sys.stdin); print('results:', len(d.get('results',[])))"
```

---

## ⚠️ 今日重建的 Sandbox 設定狀態

### 當前 openclaw.json 結構（已確認）
```json
{
    "wizard": {...},
    "agents": {
        "defaults": {
            "compaction": {"mode": "safeguard", "reserveTokens": 8000},
            "model": {"primary": "local/minimax"}
        }
    },
    "tools": {
        "web": {
            "search": {"enabled": true},
            "fetch": {"enabled": true}
        }
    },
    "gateway": {"mode": "local"},
    "models": {
        "providers": {
            "local": {
                "baseUrl": "http://host.openshell.internal:8000/v1",
                "apiKey": "ceclaw-local-key",
                "api": "openai-completions",
                "models": [
                    {
                        "id": "minimax",
                        "name": "minimax",
                        "contextWindow": 32768,
                        "maxTokens": 4096
                    }
                ]
            }
        }
    },
    "plugins": {
        "entries": {
            "searxng-search": {
                "enabled": true,
                "config": {"baseUrl": "http://host.openshell.internal:8000"}
            },
            "ceclaw": {...}
        }
    }
}
```

### 缺少的部分（待補）
- `plugins.allow` 白名單（2026.3.11 新安全要求）
- SearXNG plugin `dist/index.js` 需確認存在
- `auth-profiles.json` 位置：`/sandbox/.openclaw/agents/main/agent/auth-profiles.json`

---

## 系統環境（當前狀態）

### pop-os（主工作站）
- OS: Pop!_OS 22.04 LTS
- User: `zoe_ai`
- IP: `192.168.1.210`
- GPU: RTX 5070 Ti (16GB VRAM)
- openclaw: **2026.3.13** (pop-os 側)

### GB10（推論機）
- 硬體：NVIDIA DGX Spark，GB10 Grace Blackwell Superchip
- 統一記憶體：128GB LPDDR5X
- IP: `192.168.1.91`，User: `zoe_gb`，SSH: `ssh gb10`
- llama-server: port **8001**
- **當前模型**: Qwen3.5-122B-A10B Q4_K_M
- **start_llama.sh**：`--ctx-size 65536 --parallel 2`（#59）

### Sandbox（當前）
- sandbox name: `ceclaw-agent`
- sandbox ID: `2e04e3db-259d-4820-ae39-af385c5d0ce1` ⚠️ **今日新建，可能再變**
- openclaw 版本: **2026.3.11**（base image 決定，ARM64）
- 實際網段: `10.200.0.2`（sandbox 內），`172.19.0.2`（pop-os 視角）
- **取得最新 sandbox ID**：`ps aux | grep "openshell ssh-proxy" | grep -o "sandbox-id [a-z0-9-]*" | awk '{print $2}'`

### iptables 已加規則（今日新增，已 netfilter-persistent save）
```bash
# FORWARD
172.19.0.0/16 → 172.17.0.1:8000 ACCEPT
# INPUT  
172.19.0.0/16 → port 8000 ACCEPT
10.200.0.0/16 → port 8000 ACCEPT
# NAT
172.19.0.0/16 → 172.17.0.1 MASQUERADE
10.200.0.0/16 → 172.17.0.1 MASQUERADE
# UFW
default routed: allow（今日改）
```

---

## 重大坑記錄（今日新增）

**坑#68（關鍵）**: gateway 重建後 sandbox 消失
- 原因：`openshell gateway start` 在 gateway 已 stopped 時會重建整個 K3s，sandbox PVC 跟著消失
- 正確做法：`docker start <container_id>` 而不是 `openshell gateway start`
- 防止：每次 sandbox 設定完後立刻備份 openclaw.json 到 pop-os

**坑#69（關鍵）**: openclaw.json 必須有 `api: "openai-completions"`
- 沒有這個欄位，openclaw 不知道用什麼協議打 local Router
- TUI 顯示 `local/minimax` 但推論失敗
- 加入後立刻通

**坑#70**: sandbox 內有 `ALL_PROXY` 環境變數
- 即使 unset http_proxy/HTTP_PROXY，ALL_PROXY 還在
- curl 測試必須用 `--noproxy "*"` 才能繞過
- openclaw 用 undici（不受 ALL_PROXY 影響），所以 TUI 可以通

**坑#71**: openshell 實際網段是 `172.19.0.0/16` 不是 `172.20.0.0/16`
- 舊 SOP 的 iptables 規則漏了 `172.19.0.0/16`
- 需要加 INPUT + FORWARD + MASQUERADE 三條規則

**坑#72**: UFW `deny (routed)` 封鎖所有路由轉發
- 即使 iptables FORWARD 有 ACCEPT，UFW 的 routed deny 會覆蓋
- 解法：`sudo ufw default allow routed`

**坑#73**: restore-coredns.sh 用的是 `kubectl` 而非完整路徑
- K3s container 內 kubectl 在 `/usr/bin/kubectl`，但 docker exec 找不到
- 但實測發現 `getent hosts host.openshell.internal` 解析正確（`/etc/hosts` 寫死）
- CoreDNS 修不修不影響 DNS 解析，`host.openshell.internal` = `172.17.0.1` 是 hardcoded

**坑#74（關鍵）**: 新 sandbox 需要 `plugins.allow` 白名單（2026.3.11+）
- gateway 啟動時警告：`plugins.allow is empty; discovered non-bundled plugins may auto-load`
- 未確認是否影響 SearXNG plugin 載入

---

## 全局進度表

| # | 項目 | Phase | 狀態 | Commit |
|---|------|-------|------|--------|
| 1-35 | 歷史完成項 | P1~P5 | ✅ | — |
| 36 | 2000輪燒機 | P1 | ✅ | — |
| 37 | 503 fallback | P1 | ✅ | c894fc6 |
| 38 | SearXNG 整合 | P1 | ✅ | 328d491 |
| 39 | Qwen2.5-72B 評估 | P1 | ⬜ | — |
| 40 | reasoning 殘留 | P1 | ✗ 暫擱 | — |
| 49 | fast path ministral-3:8b | P1 | ✅ | c853e68 |
| 50 | fast path doomgrave | P1 | ✅ | 1eb09d2 |
| 51 | fast path ministral-3:14b | P1 | ✅ | 2753e28 |
| 52 | burnin_v2.sh | P1 | ✅ | 020e797 |
| 53 | Step E token guard | P1 | ✅ | a2e82d1 |
| 55 | REASONING_KEYWORDS | P1 | ✅ | bd09a17 |
| 56 | enable_thinking 注入 | P1 | ✅ | cf98b2b |
| 57 | parallel 1 修 400 | P1 | ✅ | dbc8094 |
| 58 | burnin_v3.sh Layer 2 | P1 | ✅ | 7aad6f1 |
| 59 | ctx-size 65536 + parallel 2 | P1 | ✅ | 9a0fac1 |
| 60 | fallback warning | P1 | ⬜ | — |
| 61 | 台積電/NVIDIA股價漏答 | P1 | ⬜ | — |
| 62 | gb10 retry 機制 | P1 | ⬜ | — |
| 63 | fast 路徑繁體強化 | P1 | ✅ | 512177f |
| 64 | tools 覆寫根因修復 | P1 | ✅ | b4e7ad3 |
| 65 | burnin Layer 2A 重構 | P1 | ✅ | — |
| 66 | SearXNG 穩定性盤查 | P1 | ✅ 今日 | — |
| 66b | 台灣本土模型淘汰補文件 | P1 | ⬜ | — |
| 41 | NemoClaw drop-in 驗證 | P6 | ⬜ | — |
| 42-43 | Skill 相容性測試 | P7 | ⬜ | — |
| 44 | ceclaw onboard | P8 | ⬜ | — |
| 45 | ceclaw doctor | P8 | ⬜ | — |
| 46 | ceclaw list | P8 | ⬜ | — |
| 47 | ceclaw start/stop | P8 | ⬜ | — |
| 48 | ceclaw destroy | P8 | ⬜ | — |
| 67 | Plugin OTA + 官方SDK + ceclaw update + rollback | P8 | ⬜ 新開 | — |

**完成：54 ✅ | 待做：13 ⬜ | 暫擱：1 ✗**

---

## Sandbox 重建後必做清單（已更新版）

每次重建 sandbox 後，**先在 pop-os 執行 Step E**，再進 sandbox 執行其他步驟。

### ⚠️ 先取得新 sandbox ID

```bash
# 取 sandbox ID（每次重建都會變）
SANDBOX_ID=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')
echo "SANDBOX_ID: $SANDBOX_ID"

# 若無活躍 SSH session，用以下方式
openshell sandbox list  # 確認 ceclaw-agent Ready
```

### Step E（pop-os）：Build + 傳入 plugin

```bash
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
SANDBOX_ID=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')

[ -z "$TOKEN" ] && echo "ERROR: no token" && exit 1
[ -z "$SANDBOX_ID" ] && echo "ERROR: no sandbox-id" && exit 1

# 清舊 known_hosts（sandbox 重建 host key 會變）
ssh-keygen -f "/home/zoe_ai/.ssh/known_hosts" -R "ceclaw-agent" 2>/dev/null

# Build plugin
cd /tmp && tar xzf ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz
cd openclaw-plugin-searxng
npm install
npx esbuild index.ts --bundle --format=esm --outfile=dist/index.js --external:@sinclair/typebox
ls dist/index.js && echo "build OK"

# 傳入 sandbox
scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell" \
  -o StrictHostKeyChecking=no \
  ~/ceclaw/backup/openclaw-plugin-searxng-full.tar.gz sandbox@ceclaw-agent:/tmp/

ssh -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell" \
  -o StrictHostKeyChecking=no \
  sandbox@ceclaw-agent "mkdir -p /sandbox/.openclaw/extensions/searxng-search/dist"

scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell" \
  -o StrictHostKeyChecking=no \
  /tmp/openclaw-plugin-searxng/dist/index.js sandbox@ceclaw-agent:/sandbox/.openclaw/extensions/searxng-search/dist/index.js

echo "Step E 完成"
```

### 進 sandbox 後執行（Step A → F）

```bash
openshell sandbox connect ceclaw-agent
```

```bash
# Step A: 安裝 CECLAW plugin
openclaw plugins install /opt/ceclaw

# Step B: tui alias
grep -q "alias tui=" ~/.bashrc || echo "alias tui='openclaw tui --session fresh-\$(date +%s) --history-limit 20'" >> ~/.bashrc

# Step C: openclaw.json 完整 patch（新版，含所有必要欄位）
python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))

# models
cfg["models"] = {
    "providers": {
        "local": {
            "baseUrl": "http://host.openshell.internal:8000/v1",
            "apiKey": "ceclaw-local-key",
            "api": "openai-completions",
            "models": [
                {
                    "id": "minimax",
                    "name": "minimax",
                    "contextWindow": 32768,
                    "maxTokens": 4096
                }
            ]
        }
    }
}

# gateway
if "gateway" not in cfg:
    cfg["gateway"] = {}
cfg["gateway"]["mode"] = "local"

# agents
if "agents" not in cfg:
    cfg["agents"] = {}
if "defaults" not in cfg["agents"]:
    cfg["agents"]["defaults"] = {}
cfg["agents"]["defaults"]["compaction"] = {"mode": "safeguard", "reserveTokens": 8000}
cfg["agents"]["defaults"]["model"] = {"primary": "local/minimax"}

# tools
cfg["tools"] = {
    "web": {
        "search": {"enabled": True},
        "fetch": {"enabled": True}
    }
}

# plugins allow（2026.3.11+ 新安全要求）
if "plugins" not in cfg:
    cfg["plugins"] = {}
cfg["plugins"]["allow"] = ["searxng-search", "ceclaw"]

json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("done")
EOF

# Step D: gateway auto-start（注意需要 --allow-unconfigured 如果 mode 未設定）
grep -q "openclaw gateway run" ~/.bashrc || cat >> ~/.bashrc << 'BEOF'
if ! pgrep -f "openclaw-gatewa" > /dev/null 2>&1; then
    openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
fi
BEOF

# Step F: 安裝 SearXNG plugin
cd /tmp && tar xzf openclaw-plugin-searxng-full.tar.gz
rm -rf ~/.openclaw/extensions/searxng-search 2>/dev/null
openclaw plugins install /tmp/openclaw-plugin-searxng

python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/extensions/searxng-search/package.json"
pkg = json.load(open(path))
pkg["name"] = "searxng-search"
pkg["openclaw"]["extensions"] = ["./dist/index.js"]
json.dump(pkg, open(path, "w"), indent=2, ensure_ascii=False)
print("package.json done")
EOF

python3 - << 'EOF'
import json
path = "/sandbox/.openclaw/openclaw.json"
cfg = json.load(open(path))
if "plugins" not in cfg:
    cfg["plugins"] = {}
if "entries" not in cfg["plugins"]:
    cfg["plugins"]["entries"] = {}
if "searxng-search" not in cfg["plugins"]["entries"]:
    cfg["plugins"]["entries"]["searxng-search"] = {}
entry = cfg["plugins"]["entries"]["searxng-search"]
entry["enabled"] = True
if "config" not in entry:
    entry["config"] = {}
entry["config"]["baseUrl"] = "http://host.openshell.internal:8000"
json.dump(cfg, open(path, "w"), indent=4, ensure_ascii=False)
print("openclaw.json done")
EOF

# auth（必須在 gateway 啟動前設定）
mkdir -p /sandbox/.openclaw/agents/main/agent
cat > /sandbox/.openclaw/agents/main/agent/auth-profiles.json << 'EOF'
{
    "local": {
        "apiKey": "ceclaw-local-key"
    }
}
EOF

source ~/.bashrc

# 啟動 gateway
openclaw gateway run > /tmp/openclaw-gateway.log 2>&1 &
sleep 15
cat /tmp/openclaw-gateway.log | tail -3
echo "設定完成，執行 tui 驗證"
```

### 驗證

```bash
tui
# 問：你是誰 → 我是 CECLAW 企業 AI 助手
# 問：今天台北天氣如何？ → 有搜尋結果（非 Brave API 錯誤）
```

---

## 備份 sandbox 設定（每次設定完必做）

```bash
TOKEN=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "token [a-z0-9-]*" | head -1 | awk '{print $2}')
SANDBOX_ID=$(ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}')

scp -o ProxyCommand="/usr/local/bin/openshell ssh-proxy --gateway https://127.0.0.1:8080/connect/ssh --sandbox-id $SANDBOX_ID --token $TOKEN --gateway-name openshell" \
  -o StrictHostKeyChecking=no \
  sandbox@ceclaw-agent:/sandbox/.openclaw/openclaw.json ~/ceclaw/backup/openclaw.json.bak-$(date +%Y%m%d)

echo "備份完成"
```

---

## 今日新增的 iptables 規則（已 save，重開機後自動恢復）

```bash
# 這些規則今日已加入，不需重跑
# 但若重灌 pop-os，需要加這些額外規則：

# 172.19.0.0/16（openshell container 實際網段）
sudo iptables -I FORWARD -s 172.19.0.0/16 -d 172.17.0.1 -p tcp --dport 8000 -j ACCEPT
sudo iptables -I FORWARD -s 172.19.0.0/16 -d 172.17.0.1 -p tcp --dport 8888 -j ACCEPT
sudo iptables -I INPUT -s 172.19.0.0/16 -p tcp --dport 8000 -j ACCEPT
sudo iptables -t nat -A POSTROUTING -s 172.19.0.0/16 -d 172.17.0.1 -j MASQUERADE
sudo iptables -t nat -A POSTROUTING -s 172.19.0.0/16 -j MASQUERADE

# UFW routed
sudo ufw default allow routed
sudo ufw reload

sudo netfilter-persistent save
```

---

## 關鍵指令速查

```bash
# CECLAW CLI
ceclaw status
ceclaw connect
ceclaw logs --follow

# Router 管理
sudo systemctl status/restart ceclaw-router
tail -f ~/.ceclaw/router.log

# Ollama
ollama list
ollama run ministral-3:14b "你是誰"

# GB10
ssh gb10 'sudo systemctl status llama-server'
ssh gb10 'sudo systemctl restart llama-server'
curl -s http://192.168.1.91:8001/health

# SearXNG
docker ps | grep searxng
curl -s "http://localhost:8888/search?q=test&format=json" | python3 -m json.tool | head -5
curl -s "http://localhost:8000/search?q=test&format=json" | python3 -m json.tool | head -5

# Sandbox
openshell sandbox list
openshell sandbox connect ceclaw-agent
tui

# 取 sandbox ID（動態）
ps aux | grep "openshell ssh-proxy" | grep -v grep | grep -o "sandbox-id [a-z0-9-]*" | head -1 | awk '{print $2}'

# CoreDNS restore
bash ~/nemoclaw-config/restore-coredns.sh

# 燒機
bash /tmp/burnin_v3.sh 100
```

---

## Debug SOP

### TUI auth 失敗
```
症狀：No API key found for provider "local"
解法：
1. 確認 /sandbox/.openclaw/agents/main/agent/auth-profiles.json 存在
2. 確認格式：{"local": {"apiKey": "ceclaw-local-key"}}
3. 確認 openclaw.json models.providers.local.apiKey 也有設
4. 重啟 gateway
```

### TUI 用 Brave 而非 SearXNG
```
症狀：回應說需要 Brave Search API 金鑰
解法：
1. 確認 openclaw.json tools.web.search.enabled = true
2. 確認 plugins.allow 包含 "searxng-search"
3. 確認 /sandbox/.openclaw/extensions/searxng-search/dist/index.js 存在
4. 確認 plugins.entries.searxng-search.config.baseUrl 正確
5. 重啟 gateway，看 log grep searxng
```

### Sandbox SSH 無法連線
```
症狀：kex_exchange_identification: Connection closed
解法：
1. 等 30-60 秒
2. ssh-keygen -f "~/.ssh/known_hosts" -R "ceclaw-agent"（host key 變了）
3. openshell term（TUI 方式進入）
4. 最後才重建 sandbox（需重跑 6 步）
```

### Gateway 無法啟動
```
症狀：Gateway start blocked: set gateway.mode=local
解法：確認 openclaw.json 有 "gateway": {"mode": "local"}
或臨時：openclaw gateway run --allow-unconfigured
```

### sandbox 連 Router 失敗（Connection refused）
```
症狀：curl http://host.openshell.internal:8000 無回應或 Connection refused
解法：
1. 確認 pop-os Router 在跑：ceclaw status
2. 確認 iptables 有 172.19.0.0/16 規則
3. 確認 UFW routed 是 allow
4. sandbox 內用 --noproxy "*" 測試
```

---

## 台灣本土模型評估記錄（未入文件，需記住）

| 模型 | 淘汰原因 |
|------|---------|
| taiwanllm-7b | 指令遵從差（name a color → 反問）|
| taiwanllm-13b | System prompt 洩漏、指令遵從不穩定 |
| TAIDE-8b (ryan4559) | 速度慢（cold start 2s+）、指令遵從差 |
| llama-3-taiwan-8b (cwchang) | 身份洩漏（直接說「我是 Taiwan-LLM」）|

此資料應在 #66b 補進交接文件。

---

## proxy.py 關鍵函數說明

```python
# 呼叫順序（handle_inference 內）
body = rewrite_messages(body)      # 1. role rewrite
body = inject_system_prompt(body)  # 2. 身份注入

CECLAW_SYSTEM_PROMPT = (
    "你是 CECLAW 企業 AI 助手，由 ColdElectric 提供。"
    "嚴禁提及：Qwen、qwen3、通義千問..."
    "預設使用繁體中文（台灣）回覆，嚴禁輸出簡體字。"
)
```

**_try_local()**: 逐一嘗試本地後端，健康狀態重置週期 **30 秒**（main.py `_periodic_check()`）

---

## 重要注意事項

**坑#10**: `baseUrl` 不能改成 IP，保持 `host.openshell.internal:8000/v1`
**坑#23**: 不要 `docker restart openshell container`
**坑#27**: 歷史：`--parallel 2 --ctx-size 32768` 會 400，現已改 `--ctx-size 65536 --parallel 2`
**坑#64**: openclaw gateway dynamic reload 覆寫 `tools: {}`，必須明確設 `enabled: true`
**坑#68**: gateway 重建（`openshell gateway start`）會讓 sandbox 消失
**坑#69**: openclaw.json 必須有 `api: "openai-completions"` 欄位

---

## SOP-002 工作流程

每次動手前說意圖，等 Kent 確認。格式：

> 【要改什麼】/【為什麼】/【改完 Kent 會看到什麼】

每步完成後：
```
⚠️ 記得 commit：git add -A && git commit -m "..."
```

---

## 相關連結

- OpenShell docs: https://docs.nvidia.com/openshell/latest/
- NemoClaw GitHub: https://github.com/NVIDIA/NemoClaw
- CECLAW sandbox image: ghcr.io/kentgeeng/ceclaw-sandbox:latest
- Kent GitHub: kentgeeng
- openclaw releases: https://github.com/openclaw/openclaw/releases
- GLM-5 Turbo（督察）: OpenRouter → zhipuai/glm-5-turbo

---

*CECLAW — Secure local AI agents, your inference, your rules.*
*總工: Kent | 軟工: 下個對話 Claude | 督察: GLM-5 Turbo*
*文件版本: v4.5 | 日期: 2026-03-24*
*最新狀態: TUI 身份驗證通過 ✅ | SearXNG plugin 待修 ⚠️ | 最新commit: b4e7ad3*
